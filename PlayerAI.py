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
        print(self.walls)
        turn = gameboard.current_turn

        
        return Move.NONE
