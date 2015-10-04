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
        self.easy_turrets = []
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

    def scout_turrets(self, gameboard):
        """get information on turrets for whether they can be easily killable"""
        print("scouting turrets")
        for turret in gameboard.turrets:
            print(turret.cooldown_time)
            # 1 to move in, 1 to turn, 1 to shoot (assuming adjacent to turret)
            if turret.cooldown_time > 3: # potentially 2 if we can shoot turret as it shoots back
                self.easy_turrets.append(turret)
            # ignore sniping from more than 4 squares away for now
        for turret in self.easy_turrets:
            print("easy turret at ({},{})".format(turret.x, turret.y))

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
            self.scout_turrets(gameboard)
        
        # in turret slaying mode
        if self.turret_to_slay:
            return turret_slay(gameboard, player, opponent)

        self.dist = None
        self.calc_distances(gameboard, player)
        direction = self.shortest_path(player, 10, 13)
        move = self.dir_to_move(player, direction)
                
        print("Turn %d:  %f" % (turn, 1000*(time.time() - start)))
        print(move, direction)
        print(self.dist[10][13][0])
##        for i in range(self.h):
##            for j in range(self.w):
##                print(self.dist[j][i],end='')
##            print()
        return move


    def next_pos(self, curr_pos, direction):
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
        self.dist = [[(9001,[Direction.DOWN]) for y in range(gameboard.height)] for x in range(gameboard.width)]
        self.calc_distances_propagate(gameboard, [(player.x,player.y,[player.direction])], [], 0)

    def calc_distances_propagate(self, gameboard, squares1, squares2, distance):
        next_squares1 = squares2
        next_squares2 = []
        for (x,y,d) in squares1:
            for d_propagation in list(Direction):
                x1,y1 = self.next_pos((x,y), d_propagation)
                if self.walls[x1][y1] == False:
                    if d_propagation in d:
                        if self.dist[x1][y1][0] > distance + 1:
                            next_squares1.append((x1,y1,[d_propagation]))
                        if self.dist[x1][y1][0] == distance + 1:
                            d_new = self.dist[x1][y1][1] + [d_propagation]
                            next_squares1.append((x1,y1,d_new))
                    else:
                        if self.dist[x1][y1][0] > distance + 2:
                            next_squares2.append((x1,y1,[d_propagation]))
                        if self.dist[x1][y1][0] == distance + 2:
                            d_new = self.dist[x1][y1][1] + [d_propagation]
                            next_squares2.append((x1,y1,d_new))
            self.dist[x][y] = (distance,d)
        if next_squares1 == [] and next_squares2 == []:
            return
        return self.calc_distances_propagate(gameboard, next_squares1, next_squares2, distance+1)

    def shortest_path(self, player, x, y):
        # Assumes self.dist calculated.  Returns direction in which you
        # must move to get to (x,y) in shortest turns possible.
        x0 = player.x
        y0 = player.y
        while (x != x0) or (y != y0):
            dList = self.dist[x][y][1]
            d = dList[-1]
            x,y = self.prev_pos((x,y),d)
            print(x,y)
        return d

    def dir_to_move(self, player, direction):
        if player.direction == direction:
            return Move.FORWARD
        else:
            d = {Direction.DOWN  : Move.FACE_DOWN,
                 Direction.UP    : Move.FACE_UP,
                 Direction.RIGHT : Move.FACE_RIGHT,
                 Direction.LEFT  : Move.FACE_LEFT}
            return d[direction]
            
