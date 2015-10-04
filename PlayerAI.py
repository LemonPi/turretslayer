from enum import Enum
from PythonClientAPI.libs.Game.Enums import *
from PythonClientAPI.libs.Game.MapOutOfBoundsException import *
import time

class Slay(Enum):
    PREMOVE = 0
    PRETURN = 1
    SHOOT = 2
 
class PlayerAI:
    def __init__(self):
        # Initialize any objects or variables you need here.
        self.walls = None
        self.dist = None
        self.h = None
        self.w = None
        self.bullet_incoming = False
        self.turret_to_slay = None
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
        for x in range(cur_x + 1, cur_x + 1 + arm_length):
            func(gameboard, x % w, cur_y, direction.LEFT)
        for x in range(cur_x - 1, cur_x - 1 - arm_length, -1):
            func(gameboard, x % w, cur_y, direction.RIGHT)
        for y in range(cur_y + 1, cur_y + 1 + arm_length):
            func(gameboard, cur_x, y % h, direction.DOWN)
        for y in range(cur_y - 1, cur_y - 1 - arm_length, -1):
            func(gameboard, cur_x, y % h, direction.UP)

    # cross functions go here -----------------------------------------
    def cross_no_bullet(self, gameboard, x, y, direction):
        bullets = gameboard.are_bullets_at_tile
        # check if the bullet there is headed towards you
        for b in bullets:
            if b.direction == direction:
                self.bullet_incoming = b


    def safe_to_turret_slay(self, gameboard, target_turret, player, opponent, turn, turns_req_uninterrupted):
        """true or false on whether we can enter turret slaying mode
            assumes target_turret is easily killable without moving"""

        # [fire, cooldown] period starting from 0
        period = target_turret.fire_time + target_turret.cooldown_time;
        # modulo with turn to find current phase
        phase = turn % period
        # for simplicity, assume we are adjacent to where we can fire
        # not the end of the firing cycle, disqualified automatically
        if phase != target_turret.fire_time:
            print("NO SLAY: bad phase")
            return False

        # cannot slay if about to die
        self.bullet_incoming = None
        look_at_cross(gameboard, player.x, player.y, turns_req_uninterrupted, cross_no_bullet)
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
        return True

    def turret_slay(self, gameboard, player, opponent):
        # move into position to shoot
        if self.slay_stage == Slay.PREMOVE:
            return Move.FORWARD
        # turn to face the turret
        elif self.slay_stage == Slay.PRETURN:
            if player.x < self.turret_to_slay.x:
                return Move.FACE_UP
            elif player.x > self.turret_to_slay.x:
                return Move.FACE_DOWN
            elif player.y < self.turret_to_slay.y:
                return Move.FACE_RIGHT
            else:
                return Move.FACE_LEFT
        # just shoot it
        elif self.slay_stage == Slay.SHOOT:
            self.slay_stage = Slay.GETAWAY
            # finished slaying turret
            self.slay_stage = Slay.PREMOVE
            self.turret_to_slay = None
            # get away from turret on the next move by resuming normal behaviour
            return Move.SHOOT

    def get_move(self, gameboard, player, opponent):
        # Write your AI here.
        start = time.time()
        turn = gameboard.current_turn

        if self.walls == None:
            self.calc_walls(gameboard)

        # in turret slaying mode
        if self.turret_to_slay:
            return turret_slay(gameboard, player, opponent)

        self.calc_turret_slay_sq(gameboard)
        self.calc_distances(gameboard, player)

        destination = self.calc_destination(gameboard)
        
        direction = self.shortest_path(player, destination[0], destination[1])
        move = self.dir_to_move(player, direction)

        print("Turn %d:  %f" % (turn, 1000*(time.time() - start)))
        print(move, direction)
        print(destination)
        return move

    def calc_destination(self, gameboard):
        turret_sq, turret_d = self.nearest_turret_slay_sq()
        pu_sq, pu_d = self.nearest_powerup_sq(gameboard)
        if turret_d + 2 < pu_d:
            return pu_sq
        else:
            return turret_sq

    def calc_turret_slay_sq(self, gameboard):
        self.turret_slay_sq = []
        d_perp = {Direction.UP : [Direction.LEFT, Direction.RIGHT],
                  Direction.DOWN : [Direction.LEFT, Direction.RIGHT],
                  Direction.LEFT : [Direction.UP, Direction.DOWN],
                  Direction.RIGHT : [Direction.UP, Direction.DOWN]}
        for turret in gameboard.turrets:
            tx = turret.x
            ty = turret.y
            cd = turret.cooldown_time
            #Can't kill low-cooldown turrets from within their firing
            #range (without powerups or getting shot)
            if cd <= 2:
                continue
            #Can only kill 3-cooldown turrets from direct adjacency.
            elif cd == 3:
                for d in list(Direction):
                    x1,y1 = self.next_pos((tx,ty),d)
                    if self.walls[x1][y1] == False:
                        for dp in d_perp[d]:
                            x2,y2 = self.next_pos((x1,y1),dp)
                            if self.walls[x2][y2] == False:
                                self.turret_slay_sq.append((x2,y2))
            #Can kill slow-cooldown turrets from anywhere.
            elif cd > 3:
                for d in list(Direction):
                    for i in range(4):
                        x1,y1 = self.next_pos((tx,ty),d)
                        if self.walls[x1][y1] == False:
                            for dp in d_perp[d]:
                                x2,y2 = self.next_pos((x1,y1),dp)
                                if self.walls[x2][y2] == False:
                                    self.turret_slay_sq.append((x2,y2))
                        else:
                            break
            #Can kill any turrets from beyond their shooting range.
            for d in [Direction.UP, Direction.DOWN]:
                x1,y1 = self.next_pos((tx,ty),d)
                for i in range(self.h // 2 - 1):
                    if self.walls[x1][y1] == True:
                        break
                    if i >= 4:
                        self.turret_slay_sq.append((x1,y1))
                    x1,y1 = self.next_pos((x1,y1),d)
            for d in [Direction.LEFT, Direction.RIGHT]:
                x1,y1 = self.next_pos((tx,ty),d)
                for i in range(self.w // 2 - 1):
                    if self.walls[x1][y1] == True:
                        break
                    if i >= 4:
                        self.turret_slay_sq.append((x1,y1))
                    x1,y1 = self.next_pos((x1,y1),d)

    def nearest_sq(self, squares):
        # Assumes self.dist calculated.
        closest_sq = min(squares, key=lambda sq: self.dist[sq[0]][sq[1]][0])
        dist = self.dist[closest_sq[0]][closest_sq[1]][0]
        return closest_sq, dist

    def nearest_turret_slay_sq(self):
        return self.nearest_sq(self.turret_slay_sq)

    def nearest_powerup_sq(self, gameboard):
        pu_squares = [(pu.x, pu.y) for pu in gameboard.power_ups]
        return self.nearest_sq(pu_squares)

    def next_pos(self, curr_pos, direction):
        ''' Get coordinates of the square in direction of current_pos. '''
        x,y = curr_pos
        if direction == Direction.DOWN:
            return (x, (y+1)%self.h)
        elif direction == Direction.UP:
            return (x, (y-1)%self.h)
        elif direction == Direction.RIGHT:
            return ((x+1)%self.w, y)
        elif direction == Direction.LEFT:
            return ((x-1)%self.w, y)

    def prev_pos(self, curr_pos, direction):
        ''' Get coordinates of the square in the opposite direction of
        curr_pos. I.e. moving in direction from prev_pos gets you to
        curr_pos. '''
        x,y = curr_pos
        if direction == Direction.DOWN:
            return (x, (y-1)%self.h)
        elif direction == Direction.UP:
            return (x, (y+1)%self.h)
        elif direction == Direction.RIGHT:
            return ((x-1)%self.w, y)
        elif direction == Direction.LEFT:
            return ((x+1)%self.w, y)

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
            d = dList[-1]
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
            
