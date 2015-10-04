from PythonClientAPI.libs.Game.Enums import *
from PythonClientAPI.libs.Game.MapOutOfBoundsException import *

class PlayerAI:
    def __init__(self):
        # Initialize any objects or variables you need here.
        self.walls = None
        pass

    def calc_walls(self, gameboard):
        self.walls = [[False for y in range(gameboard.height)] for x in range(gameboard.width)]
        for wall in gameboard.walls:
            self.walls[wall.x][wall.y] = True
        for turret in gameboard.turrets:
            self.walls[turret.x][turret.y] = True

    def get_move(self, gameboard, player, opponent):
        # Write your AI here.
        if self.walls == None:
            self.calc_walls(gameboard)
            self.calc_distances(gameboard, player)
            for row in self.dist:
                print(row)
            print()
            for j in range(len(self.dist[0])):
                for i in range(len(self.dist)):
                    print(self.dist[i][j],end='')
                print()
                
        
        turn = gameboard.current_turn

        
        return Move.NONE

    def calc_distances(self, gameboard, player):
        self.dist = [[(9001,Direction.DOWN) for y in range(gameboard.height)] for x in range(gameboard.width)]
        self.calc_distances_propagate(gameboard, [(player.x,player.y,player.direction)], [], 0)

    def calc_distances_propagate(self, gameboard, squares1, squares2, distance):
        next_squares1 = squares2
        next_squares2 = []
        h = gameboard.height
        w = gameboard.width
        for (x,y,d) in squares1:
            x1 = (x+1)%w
            x2 = (x-1)%w
            y1 = (y+1)%h
            y2 = (y-1)%h
            #down
            if self.walls[x][y1] == False:
                if d == Direction.DOWN:
                    if self.dist[x][y1][0] >= distance + 1:
                        next_squares1.append((x,y1,Direction.DOWN))
                else:
                    if self.dist[x][y1][0] >= distance + 2:
                        next_squares2.append((x,y1,Direction.DOWN))
            #up
            if self.walls[x][y2] == False:
                if d == Direction.UP:
                    if self.dist[x][y2][0] >= distance + 1:
                        next_squares1.append((x,y2,Direction.UP))
                else:
                    if self.dist[x][y2][0] >= distance + 2:
                        next_squares2.append((x,y2,Direction.UP))
            #right
            if self.walls[x1][y] == False:
                if d == Direction.RIGHT:
                    if self.dist[x1][y][0] >= distance + 1:
                        next_squares1.append((x1,y,Direction.RIGHT))
                else:
                    if self.dist[x1][y][0] >= distance + 2:
                        next_squares2.append((x1,y,Direction.RIGHT))
            #left
            if self.walls[x2][y] == False:
                if d == Direction.LEFT:
                    if self.dist[x2][y][0] >= distance + 1:
                        next_squares1.append((x2,y,Direction.LEFT))
                else:
                    if self.dist[x2][y][0] >= distance + 2:
                        next_squares2.append((x2,y,Direction.LEFT))
            self.dist[x][y] = (distance,d)
        if next_squares1 == [] and next_squares2 == []:
            return
        return self.calc_distances_propagate(gameboard, next_squares1, next_squares2, distance+1)
