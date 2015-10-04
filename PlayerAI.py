from PythonClientAPI.libs.Game.Enums import *
from PythonClientAPI.libs.Game.MapOutOfBoundsException import *
import time

class PlayerAI:
    def __init__(self):
        # Initialize any objects or variables you need here.
        self.walls = None
        self.dist = None
        pass

    def calc_walls(self, gameboard):
        self.h = gameboard.height
        self.w = gameboard.width
        
        self.walls = [[False for y in range(gameboard.height)] for x in range(gameboard.width)]
        for wall in gameboard.walls:
            self.walls[wall.x][wall.y] = True
        for turret in gameboard.turrets:
            self.walls[turret.x][turret.y] = True

    def get_move(self, gameboard, player, opponent):
        # Write your AI here.
        start = time.time()
        turn = gameboard.current_turn

        if self.walls == None:
            self.calc_walls(gameboard)
        
        self.dist = None
        self.calc_distances(gameboard, player)
        direction = self.shortest_path(player, 10, 13)
        move = self.dir_to_move(player, direction)
                
        print("Turn %d:  %f" % (turn, 1000*(time.time() - start)))
#        print("elapsed: {}".format(1000*(time.time() - start)))
        print(move, direction)
        print(self.dist[10][13][0])
##        for i in range(self.h):
##            for j in range(self.w):
##                print(self.dist[j][i],end='')
##            print()
        return move
        return Move.NONE

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
            
