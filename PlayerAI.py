from PythonClientAPI.libs.Game.Enums import *
from PythonClientAPI.libs.Game.MapOutOfBoundsException import *
import time

class PlayerAI:
    def __init__(self):
        # Initialize any objects or variables you need here.
        self.walls = None
        self.easy_turrets = []
        pass

    def calc_walls(self, gameboard):
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

    def get_move(self, gameboard, player, opponent):
        # Write your AI here.
        start = time.time()

        if self.walls == None:
            self.calc_walls(gameboard)
            self.scout_turrets(gameboard)

        self.calc_distances(gameboard, player)
        # print(self.dist)
        
        turn = gameboard.current_turn

        print("elapsed: {}".format(1000*(time.time() - start)))
        return Move.NONE

    def calc_distances(self, gameboard, player):
        self.dist = [[9001 for y in range(gameboard.height)] for x in range(gameboard.width)]
        self.calc_distances_propagate(gameboard, [(player.x,player.y)], 0)

    def calc_distances_propagate(self, gameboard, squares, distance):
        next_squares = []
        h = gameboard.height
        w = gameboard.width
        for (x,y) in squares:
            x1 = (x+1)%w
            x2 = (x-1)%w
            y1 = (y+1)%h
            y2 = (y-1)%h
            if self.walls[x][y1] == False:
                if self.dist[x][y1] > distance:
                    next_squares.append((x,y1))
            if self.walls[x][y2] == False:
                if self.dist[x][y2] > distance:
                    next_squares.append((x,y2))
            if self.walls[x1][y] == False:
                if self.dist[x1][y] > distance:
                    next_squares.append((x1,y))
            if self.walls[x2][y] == False:
                if self.dist[x2][y] > distance:
                    next_squares.append((x2,y))
            self.dist[x][y] = distance
        if next_squares == []:
            return
        return self.calc_distances_propagate(gameboard, next_squares, distance+1)
