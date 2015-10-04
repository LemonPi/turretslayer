from enum import Enum
from PythonClientAPI.libs.Game.Enums import *
from PythonClientAPI.libs.Game.MapOutOfBoundsException import *
import time


d_perp = {Direction.UP : [Direction.LEFT, Direction.RIGHT],
          Direction.DOWN : [Direction.LEFT, Direction.RIGHT],
          Direction.LEFT : [Direction.UP, Direction.DOWN],
          Direction.RIGHT : [Direction.UP, Direction.DOWN]}
d_opp =  {Direction.UP : Direction.DOWN,
          Direction.DOWN : Direction.UP,
          Direction.LEFT : Direction.RIGHT,
          Direction.RIGHT : Direction.LEFT}

class Slay(Enum):
    PREMOVE = 0
    PRETURN = 1
    SHOOT = 2

    SLAY_MODE = 3

 
class PlayerAI:
    def __init__(self):
        # Initialize any objects or variables you need here.
        self.walls = None
        self.dist = None
        self.h = None
        self.w = None
        self.turret_slay_sq = {} # (x,y):turret dictionary
        self.bullet_incoming = False
        self.turret_to_slay = None
        self.slay_stage = Slay.PREMOVE
        self.turn_to_slay = False

        self.live_turret_num = 0
        self.mexican_standoff_turns = 0
        pass

    def calc_walls(self, gameboard):
        self.h = gameboard.height
        self.w = gameboard.width
        
        self.walls = [[False for y in range(gameboard.height)] for x in range(gameboard.width)]
        for wall in gameboard.walls:
            self.walls[wall.x][wall.y] = True
        for turret in gameboard.turrets:
            self.walls[turret.x][turret.y] = True

    def look_at_cross(self, gameboard, cur_x, cur_y, arm_length, func):
        # assumes cur_x and cur_y are % w and h
        # gives the direction towards cur_x and cur_y from arm
        h = self.h
        w = self.w
        for x in range(cur_x + 1, cur_x + 1 + arm_length):
            func(gameboard, x % w, cur_y, Direction.LEFT)
        for x in range(cur_x - 1, cur_x - 1 - arm_length, -1):
            func(gameboard, x % w, cur_y, Direction.RIGHT)
        for y in range(cur_y + 1, cur_y + 1 + arm_length):
            func(gameboard, cur_x, y % h, Direction.UP)
        for y in range(cur_y - 1, cur_y - 1 - arm_length, -1):
            func(gameboard, cur_x, y % h, Direction.DOWN)

    # cross functions go here -----------------------------------------
    def cross_no_bullet(self, gameboard, x, y, direction):
        # print("checking bullets ({},{})".format(x,y))
        bullets = gameboard.are_bullets_at_tile(x, y)
        # check if the bullet there is headed towards you
        for b in bullets:
            # print("found bullet going {}".format(b.direction))
            if b.direction == direction:
                self.bullet_incoming = b
                break


    def safe_to_turret_slay(self, gameboard, target_turret, player, opponent, turn, turns_req_uninterrupted):
        """true or false on whether we can enter turret slaying mode
            assumes target_turret is easily killable without moving"""


        # can't slay if facing the wrong way (don't need to modulo since turret is inside grid)
        if not self.turn_to_slay:
            if player.direction != Direction.RIGHT and target_turret.x == player.x + 1 and not self.walls[player.x+1][player.y]:
                print("NO SLAY: face right")
                self.turn_to_slay = True
                return Move.FACE_RIGHT
            if player.direction != Direction.LEFT and target_turret.x == player.x - 1 and not self.walls[player.x-1][player.y]:
                print("NO SLAY: face left")
                self.turn_to_slay = True
                return Move.FACE_LEFT
            if player.direction != Direction.UP and target_turret.y == player.y - 1 and not self.walls[player.x][player.y-1]:
                print("NO SLAY: face up")
                self.turn_to_slay = True
                return Move.FACE_UP
            if player.direction != Direction.DOWN and target_turret.y == player.y + 1 and not self.walls[player.x][player.y+1]:
                print("NO SLAY: face down")
                self.turn_to_slay = True
                return Move.FACE_DOWN


        # [fire, cooldown] period starting from 0
        period = target_turret.fire_time + target_turret.cooldown_time;
        # modulo with turn to find current phase
        phase = turn % period
        # for simplicity, assume we are adjacent to where we can fire
        # not the end of the firing cycle, disqualified automatically
        if phase != target_turret.fire_time:
            print("NO SLAY: bad phase")
            return Move.NONE

        # cannot slay if about to die
        self.bullet_incoming = None
        self.look_at_cross(gameboard, player.x, player.y, turns_req_uninterrupted, self.cross_no_bullet)
        if self.bullet_incoming:
            print("NO SLAY: bullet incoming ({},{})".format(self.bullet_incoming.x, self.bullet_incoming.y))
            return False

        # dangerous if opponent can get to us
        # NOTE self.dist is from self to the other object, which is only an approximation of the distance
        if self.dist[opponent.x][opponent.y][0] < turns_req_uninterrupted:
            print("NO SLAY: opponent too close")
            return False

        # dangerous if opponent teloports in while turret slaying
        if opponent.teleport_count:
            tele_in = gameboard.teleport_locations
            for tele in tele_in:
                # distance that either the opponent or their bullet can close + 1 turn for teleport usage
                if self.dist[tele.x][tele.y][0] + 1 < turns_req_uninterrupted:
                    print("NO SLAY: opponent can teleport in")
                    return False
        return Slay.SLAY_MODE


    def turret_slay(self, gameboard, player, opponent):
        # move into position to shoot
        if self.slay_stage == Slay.PREMOVE:
            print("Moving forward")
            self.slay_stage = Slay.PRETURN
            return Move.FORWARD
        # turn to face the turret
        elif self.slay_stage == Slay.PRETURN:
            print("Turning to shoot")
            self.slay_stage = Slay.SHOOT
            if player.x < self.turret_to_slay.x:
                return Move.FACE_RIGHT
            elif player.x > self.turret_to_slay.x:
                return Move.FACE_LEFT
            elif player.y < self.turret_to_slay.y:
                return Move.FACE_DOWN
            else:
                return Move.FACE_UP
        # just shoot it
        elif self.slay_stage == Slay.SHOOT:
            print("Shooting")
            # finished slaying turret
            self.slay_stage = Slay.PREMOVE
            self.turret_to_slay = None
            self.turn_to_slay = False
            # get away from turret on the next move by resuming normal behaviour
            return Move.SHOOT

    def get_move(self, gameboard, player, opponent):
        # Write your AI here.
        start = time.time()
        turn = gameboard.current_turn

        if self.walls == None:
            self.calc_walls(gameboard)

        self.update_live_turrets(gameboard)

        # reached a turret slaying squre
        if (player.x, player.y) in self.turret_slay_sq:
            target_turret = self.turret_slay_sq[(player.x, player.y)]
            turns_req = 4 # enter turn shoot turn away
            if self.is_adjacent(player, target_turret.x, target_turret.y):
                turns_req = 3

            slay_move = self.safe_to_turret_slay(gameboard, target_turret, player, opponent, turn, turns_req)
            if slay_move == Slay.SLAY_MODE:
                print("entering turret slaying mode")
                self.turret_to_slay = target_turret
            elif slay_move:
                print("safely preparing for slaying")
                return slay_move

        # in turret slaying mode, ignore other tasks
        if self.turret_to_slay:
            return self.turret_slay(gameboard, player, opponent)

        self.calc_distances(gameboard, player)

        destination = self.calc_destination(gameboard)
        
        direction = self.shortest_path(player, destination[0], destination[1])
        move = self.dir_to_move(player, direction)
        print(move)
        move = self.QA_move(gameboard, player, opponent, move)
        print(move)

##        for i in range(len(self.dist)):
##            for j in range(len(self.dist[0])):
##                print(self.dist[j][i],end='')
##            print()

        print("Turn %d:  %f" % (turn, 1000*(time.time() - start)))
        # print(move, direction)
        print(destination)
        return move

    def is_safe_from_turretfire(self, x1, y1, gameboard):
        h = self.h
        w = self.w
        for turret in gameboard.turrets:
            if turret.is_firing_next_turn:
                # turret about to be destroyed, don't worry about it
                self.bullet_incoming = None
                self.look_at_cross(gameboard, turret.x, turret.y, 1, self.cross_no_bullet)
                if self.bullet_incoming:
                    print("turret at ({},{}) about to die, ignore".format(turret.x, turret.y))
                    continue

                tx = turret.x
                ty = turret.y
                if tx == x1:
                    #checks if you're above/below/right/left of turret, and in range and not blocked by a wall
                    #up
                    for y in range(ty-1, ty-5, -1):
                        if self.walls[tx][y % h] == True:
                            break
                        if y == y1:
                            #BAD - TURRETFIRE
                            return False
                    #down
                    for y in range(ty+1, ty+5):
                        if self.walls[tx][y % h] == True:
                            break
                        if y == y1:
                            #BAD - TURRETFIRE
                            return False
                if ty == y1:
                    #right
                    for x in range(tx-1, tx-5, -1):
                        if self.walls[x % w][ty] == True:
                            break
                        if x == x1:
                            #BAD - TURRETFIRE
                            return False
                    #left
                    for x in range(tx+1, tx+5):
                        if self.walls[x % w][ty] == True:
                            break
                        if x == x1:
                            #BAD - TURRETFIRE
                            return False
        return True

    def QA_move(self, gameboard, player, opponent, move):
        ''' Safety-related overrides. '''
        if move == Move.FORWARD:
            (x1,y1) = self.next_pos((player.x, player.y), player.direction)
            #Avoid turretfire.
            if not self.is_safe_from_turretfire(x1, y1, gameboard):
                return Move.SHOOT
            #Avoid bullets
            for bullet in gameboard.bullets:
                if bullet.direction == d_opp[player.direction]:
                    #Bullet right in front of you - RUN!
                    if (bullet.x, bullet.y) == (x1,y1):
                        if player.teleport != 0:
                            return Move.TELEPORT_0 #todo - find best teleport location
                        elif player.shield != 0:
                            return Move.SHIELD
                        else:
                            return move #nothing to be done; take the damage and go on your merry way.
                    elif self.next_pos((bullet.x, bullet.y), bullet.direction, n=2) == (x1,y1):
                        #Bullet coming at you from 3 squares away - turn away
                        for d in d_perp[bullet.direction]:
                            x2,y2 = self.next_pos((player.x,player.y), d)
                            if self.walls[x2][y2] == False:
                                return self.dir_to_move(d)
                if self.next_pos((bullet.x, bullet.y), bullet.direction) == (x1,y1):
                    #Bullet coming at you from 2 squares away - turn away
                    if player.direction not in d_perp[bullet.direction]:
                        for d in d_perp[bullet.direction]:
                            x2,y2 = self.next_pos((player.x,player.y), d)
                            if self.walls[x2][y2] == False:
                                return self.dir_to_move(d)
                        else:
                            #Nowhere to turn - RUN!
                            if player.teleport != 0:
                                return Move.TELEPORT_0 #todo - find best teleport location
                            elif player.shield != 0:
                                return Move.SHIELD
                            else:
                                return move #nothing to be done; take the damage and go on your merry way. 
                    # Bullet on perpendicular path to hit. Just wait. 
                    else:
                        return Move.SHOOT
            #Avoid the square right in front of opponent - his shot would hit you with no warning.
            #But, there's also risk of a mexican standoff, with no one moving.  Only spend 2 turns shooting. 
            if (x1,y1) == self.next_pos((opponent.x, opponent.y), opponent.direction):
                if self.mexican_standoff_turns < 2:
                    self.mexican_standoff_turns += 1
                    return Move.SHOOT
                else:
                    for d in list(Direction):
                        if d == player.direction:
                            continue
                        x2,y2 = self.next_pos((player.x,player.y), d)
                        if self.walls[x2][y2] == False:
                            return self.dir_to_move(d)
        #If you don't move, check that you won't get injured. 
        elif move in [Move.FACE_LEFT, Move.FACE_RIGHT, Move.FACE_DOWN, Move.FACE_UP]:
            x1,y1 = (player.x, player.y)
            if not self.is_safe_from_turretfire(x1, y1, gameboard):
                x2,y2 = self.next_pos((x1,y1), player.direction)
                if self.walls[x2][y2] == False:
                    return Move.FORWARD
                elif player.teleport != 0:
                    return Move.TELEPORT_0 #todo - find best teleport location
                elif player.shield != 0:
                    return Move.SHIELD
                else:
                    return move #nothing to be done; take the damage and go on your merry way.
            #Avoid unavoidable bullets (coming right at you from 1 square)
            for bullet in gameboard.bullets:
                if bullet.direction == d_opp[player.direction]:
                    #Bullet right in front of you - RUN!
                    if (bullet.x, bullet.y) == (x1,y1):
                        if player.teleport != 0:
                            return Move.TELEPORT_0 #todo - find best teleport location
                        elif player.shield != 0:
                            return Move.SHIELD
                        else:
                            return move #nothing to be done; take the damage and go on your merry way.
        #All seems well.  No overrides. 
        return move


    def calc_destination(self, gameboard):
        turret_sq, turret_d = self.nearest_turret_slay_sq()
        pu_sq, pu_d = self.nearest_powerup_sq(gameboard)
        print('distances', pu_d, turret_d)
        if turret_d + 1 < pu_d:
            return turret_sq
        else:
            return pu_sq

    def update_live_turrets(self, gameboard):
        new_live_turret_num = 0
        for turret in gameboard.turrets:
            if not turret.is_dead:
                new_live_turret_num += 1

        # some turret died
        if new_live_turret_num != self.live_turret_num:
            live_turret_num = new_live_turret_num
            self.calc_turret_slay_sq(gameboard)


    def calc_turret_slay_sq(self, gameboard):
        # reset to get rid of dead ones
        self.turret_slay_sq = {}

        for turret in gameboard.turrets:
            if turret.is_dead:
                continue
            tx = turret.x
            ty = turret.y
            cd = turret.cooldown_time
            #Can't kill low-cooldown turrets from within their firing
            #range (without powerups or getting shot)
            if cd <= 1:
                continue
            #Can only kill 3-cooldown turrets from direct adjacency.
            elif cd <= 2:
                for d in list(Direction):
                    x1,y1 = self.next_pos((tx,ty),d)
                    if self.walls[x1][y1] == False:
                        for dp in d_perp[d]:
                            x2,y2 = self.next_pos((x1,y1),dp)
                            if self.walls[x2][y2] == False:
                                self.turret_slay_sq[(x2,y2)] = turret
            #Can kill slow-cooldown turrets from anywhere.
            elif cd > 2:
                for d in list(Direction):
                    for i in range(4):
                        x1,y1 = self.next_pos((tx,ty),d,n=i+1)
                        if self.walls[x1][y1] == False:
                            for dp in d_perp[d]:
                                x2,y2 = self.next_pos((x1,y1),dp)
                                if self.walls[x2][y2] == False:
                                    self.turret_slay_sq[(x2,y2)] = turret
                        else:
                            break
            #Can kill any turrets from beyond their shooting range.
            for d in [Direction.UP, Direction.DOWN]:
                x1,y1 = self.next_pos((tx,ty),d)
                for i in range(self.h // 2 - 1):
                    if self.walls[x1][y1] == True:
                        break
                    if i >= 4:
                        self.turret_slay_sq[(x1,y1)] = turret
                    x1,y1 = self.next_pos((x1,y1),d)
            for d in [Direction.LEFT, Direction.RIGHT]:
                x1,y1 = self.next_pos((tx,ty),d)
                for i in range(self.w // 2 - 1):
                    if self.walls[x1][y1] == True:
                        break
                    if i >= 4:
                        self.turret_slay_sq[(x1,y1)] = turret
                    x1,y1 = self.next_pos((x1,y1),d)

    def nearest_sq(self, squares):
        # Assumes self.dist calculated.
        closest_sq = min(squares, key=lambda sq: self.dist[sq[0]][sq[1]][0])
        dist = self.dist[closest_sq[0]][closest_sq[1]][0]
        return closest_sq, dist

    def nearest_sq_dict(self, squares):
        # For dictionaries with keys as (x,y):turret
        closest_sq = min(squares.keys(), key=lambda sq: self.dist[sq[0]][sq[1]][0])
        dist = self.dist[closest_sq[0]][closest_sq[1]][0]
        return closest_sq, dist

    def nearest_turret_slay_sq(self):
        # nearest_sq but for dictionary
        return self.nearest_sq_dict(self.turret_slay_sq)

    def nearest_powerup_sq(self, gameboard):
        pu_squares = [(pu.x, pu.y) for pu in gameboard.power_ups]
        return self.nearest_sq(pu_squares)

    def next_pos(self, curr_pos, direction, n=1):
        ''' Get coordinates of the square in direction of current_pos. '''
        x,y = curr_pos
        if direction == Direction.DOWN:
            return (x, (y+n)%self.h)
        elif direction == Direction.UP:
            return (x, (y-n)%self.h)
        elif direction == Direction.RIGHT:
            return ((x+n)%self.w, y)
        elif direction == Direction.LEFT:
            return ((x-n)%self.w, y)

    def prev_pos(self, curr_pos, direction, n=1):
        ''' Get coordinates of the square in the opposite direction of
        curr_pos. I.e. moving in direction from prev_pos gets you to
        curr_pos. '''
        x,y = curr_pos
        if direction == Direction.DOWN:
            return (x, (y-n)%self.h)
        elif direction == Direction.UP:
            return (x, (y+n)%self.h)
        elif direction == Direction.RIGHT:
            return ((x-n)%self.w, y)
        elif direction == Direction.LEFT:
            return ((x+n)%self.w, y)

    def calc_distances(self, gameboard, player):
        ''' Magic.  Produces self.dist - a 2D array corresponding to the
        game map, with each cell containint (dist, dirList), where dist
        is the number of turns to get from the player's current position
        to that cell, and dirList is a list of possible final
        orientations / last moves taken to do this in the shortest
        amount of time.

        This array can be used to reconstruct the shortest path from the
        player to any cell, as well as for accurate distance
        measurements. '''
        self.dist = [[(9001,[Direction.DOWN]) for y in range(gameboard.height)] for x in range(gameboard.width)]
        self.calc_distances_propagate(gameboard, {(player.x,player.y) : [player.direction]}, {}, 0)

    def calc_distances_propagate(self, gameboard, squares1, squares2, distance):
        ''' The details:  every square is either 1 turn away or 2 turns
        away, depending on player's current orientation relative to the
        direction of that square.  Thus, we increment distances and
        spread the net of 'reached' squares (keeping track of
        orientation along the shortest paths to deal with above), until
        we've reached all reachable squares.

        squares1, squares2 = {(x,y) : [dList]}, where (x,y) is cell
        coordinate, and dList is the list of directions from which you
        can arrive at this cell along a shortest path (may be multiple). '''
        for pos in squares1:
            squares2.pop(pos,None)
        next_squares1 = squares2
        next_squares2 = {}
        for pos, dList in squares1.items():
            x,y = pos
            for d_propagation in list(Direction):
                x1,y1 = self.next_pos((x,y), d_propagation)
                if self.walls[x1][y1] == False:
                    if d_propagation in dList:
                        if self.dist[x1][y1][0] > distance + 1:
                            if (x1,y1) in next_squares1:
                                next_squares1[(x1,y1)] += [d_propagation]
                            else:
                                next_squares1[(x1,y1)] = [d_propagation]
                        if self.dist[x1][y1][0] == distance + 1:
                            d_new = self.dist[x1][y1][1] + [d_propagation]
                            if (x1,y1) in next_squares1:
                                next_squares1[(x1,y1)] += d_new
                            else:
                                next_squares1[(x1,y1)] = d_new
                    else:
                        if self.dist[x1][y1][0] > distance + 2:
                            if (x1,y1) in next_squares2:
                                next_squares2[(x1,y1)] += [d_propagation]
                            else:
                                next_squares2[(x1,y1)] = [d_propagation]
                        if self.dist[x1][y1][0] == distance + 2:
                            d_new = self.dist[x1][y1][1] + [d_propagation]
                            if (x1,y1) in next_squares2:
                                next_squares2[(x1,y1)] += d_new
                            else:
                                next_squares2[(x1,y1)] = d_new
            self.dist[x][y] = (distance,dList)
        if len(next_squares1) == 0 and len(next_squares2) == 0:
            return
        return self.calc_distances_propagate(gameboard, next_squares1, next_squares2, distance+1)

    def shortest_path(self, player, x, y):
        # Assumes self.dist calculated.  Returns direction in which you
        # must move to get to (x,y) in shortest turns possible.  Assumes you have not reached target. 
        x0 = player.x
        y0 = player.y
        while (x != x0) or (y != y0):
            dList = self.dist[x][y][1]
            d = dList[0]
            x,y = self.prev_pos((x,y),d)
        return d

    def dir_to_move(self, player, direction):
        ''' Converts desired Direction enum into a Move enum, accounting
        for player's orientation. '''
        if player.direction == direction:
            return Move.FORWARD
        else:
            d = {Direction.DOWN  : Move.FACE_DOWN,
                 Direction.UP    : Move.FACE_UP,
                 Direction.RIGHT : Move.FACE_RIGHT,
                 Direction.LEFT  : Move.FACE_LEFT}
            return d[direction]

    def is_adjacent(self, player, x, y):
        return abs(player.x - x) <= 1 and abs(player.y - y) <= 1
