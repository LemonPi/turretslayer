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
tp_index_to_move = {0:Move.TELEPORT_0, 1:Move.TELEPORT_1, 
                    2:Move.TELEPORT_2, 3:Move.TELEPORT_3, 
                    4:Move.TELEPORT_4, 5:Move.TELEPORT_5}


class Slay(Enum):
    ''' States in turret slaying mode. '''
    PREMOVE = 0
    PRETURN = 1
    SHOOT = 2

    SLAY_MODE = 3


def print_debug(*arg):
    ''' Prints in debug mode and does nothing in production. '''
    # print(*arg)
    return
 

class PlayerAI:
    def __init__(self):
        ''' Initializes internal state without doing any real work since gameboard is not passed in. '''
        self.walls = None
        self.dist = None
        self.h = None
        self.w = None
        self.turret_slay_sq = {} # (x,y):turret dictionary
        self.last_turret_slay_sq = None

        self.bullet_incoming = False
        self.turret_to_slay = None
        self.preparing_slay_mode = None # Move indicating what to do before ready for turret slaying
        self.slay_stage = Slay.PREMOVE


        self.learn_opp_defense = False
        self.opp_shield_tp = 0
        self.opp_isnt_defensive_vs_laser = False
        self.learn_opp_offense = False
        self.opp_lasers = 0
        self.opp_is_aggro_vs_shield = False

        self.live_turret_num = 0
        self.mexican_standoff_turns = 0
        pass


    def get_move(self, gameboard, player, opponent):
        '''
        Decide on the best move to take in this turn, always returns a valid Move commands.

        High level description of our method:
        - Try to learn how opponent bots act under pressure
        - Build shortest path to everywhere with incoming direction information (allows traceback)
        - Plan to take out turrets by marking squares that allow us to kill without taking a hit
            - low cooldown turrets need adjacent corner squares (shot from directly adjacent squares)
            - high cooldown turrets can be shot from anywhere
        - Plan to retrieve powerups by marking those squares
        - Prioritize turrets by giving powerup squares slight distance-value penalty
        - If opponent encountered within laser range, consider using powerups 
            (use life resource to determine opponent behaviour to gain long term advantage)
        - Get destination by considering the closest marked squares
        - Traceback from destination along shortest path to get next move

        Powerup usage:
        - Leverage knowledge of opponent behaviour to efficiently use powerups
        - If opponent overly defensive, reserve powerups while waiting for them to waste theirs
        - If opponent overly aggressive, use shield as a 2 for 1 (1 powerup for 1 powerup and 1 opponent health)
        - Only use powerup when either you or opponent is in danger (against turrets can efficiently kill with just bullets)
        - Teleport as last resort
        '''

        print_debug('...')
        start = time.time()
        turn = gameboard.current_turn
        if self.learn_opp_defense:
            # If opponent used a shield or a teleport last turn, he's overly cautious, and I don't have to use my laser to make him use up his defence. 
            self.opp_isnt_defensive_vs_laser = not bool(self.opp_shield_tp - opponent.shield_count - opponent.teleport_count)
            self.learn_opp_defense = False
        if self.learn_opp_offense:
            # If opponent shot a laser last turn, he takes risks while I hold a shield.  Will take advantage of this next time. 
            self.opp_is_aggro_vs_shield = bool(self.opp_lasers - opponent.laser_count)
            self.learn_opp_offense = False

        if self.walls == None:
            self.calc_walls(gameboard)

        self.update_live_turrets(gameboard)

        # reached a turret slaying squre
        if (player.x, player.y) in self.turret_slay_sq:
            target_turret = self.turret_slay_sq[(player.x, player.y)]
            turns_req = 4 # enter turn shoot turn away
            if self.is_adjacent(player, target_turret.x, target_turret.y):
                turns_req = 3

            self.prepare_to_turret_slay(gameboard, target_turret, player, opponent, turn, turns_req)
            if not self.preparing_slay_mode: # finished all preparation
                self.turret_to_slay = target_turret
        else:
            self.preparing_slay_mode = None


        # do not interrupt turret killing in the middle of it
        if self.slay_stage in {Slay.PRETURN, Slay.SHOOT}:
            print_debug("uninterrupted slaying mode")
            return self.turret_slay(gameboard, player, opponent)

        # update actual distances to everything
        self.calc_distances(gameboard, player)

        # use a powerup if opportunity presents itself (someone is in danger)
        powerup_move = self.consider_powering_up(gameboard, player, opponent)
        if powerup_move is not None:
            return powerup_move


        # preparing for turret slaying (do this before starting slaying mode, when finished preparations should be None)
        if not self.preparing_slay_mode is None:
            print_debug("safely preparing for slaying")
            return self.preparing_slay_mode

        # entering turret slaying mode, ignore other tasks while doing so
        if self.turret_to_slay:
            print_debug("entering turret slaying mode")
            # finished preparing
            self.preparing_slay_mode = None
            return self.turret_slay(gameboard, player, opponent)
        
        
        # If opp directly in front of me after dealing with issues of my survival, shoot him. 
        if self.next_pos((player.x,player.y), player.direction) == (opponent.x,opponent.y):
            return Move.SHOOT
        
        destination = self.calc_destination(gameboard, opponent)
        
        direction = self.shortest_path(player, destination[0], destination[1])
        move = self.dir_to_move(player, direction)
        print_debug(move)
        move = self.QA_move(gameboard, player, opponent, move)
        print_debug(move)


        print_debug("Turn %d:  %f" % (turn, 1000*(time.time() - start)))
        print_debug(destination)
        return move


    def run_for_the_hills(self, gameboard):
        ''' Decide which teleport location to escape to; always returns a valid Move order '''
        close_tp_locs = sorted(enumerate(gameboard.teleport_locations), key=lambda x: self.dist[x[1][0]][x[1][1]][0])
        
        # go for the 2nd closest if possible, which is more likely to be safe else use closest
        if len(close_tp_locs) > 1:
            return tp_index_to_move[close_tp_locs[1][0]]
        elif len(close_tp_locs) == 1:
            return tp_index_to_move[close_tp_locs[0][0]]
        # if there are no teleport locations, good maps should not have teleport powerups, but just in case...
        else:
            return Move.NONE


    def consider_powering_up(self, gameboard, player, opponent):
        '''
        Check whether a powerup should be used at this moment and return either a Move order or None.
        Use a powerup if somebody is in danger (either need to escape or can score a hit).
        '''
        me_in_danger = not (self.is_safe_from_laser(player, opponent) or player.shield_active) and opponent.laser_count != 0
        opp_in_danger = not (self.is_safe_from_laser(opponent, player) or opponent.shield_active) and player.laser_count != 0
        if me_in_danger and opp_in_danger:
            #Survival is primary concern.  After that is learning the opponent's programming.
            if self.opp_is_aggro_vs_shield:
                if player.shield_count != 0:
                    return Move.SHIELD
            if self.opp_isnt_defensive_vs_laser:
                if player.laser_count != 0:
                    return Move.LASER
            if player.hp == 1:
                if player.shield_count != 0:
                    return Move.SHIELD
                elif player.teleport_count != 0:
                    return self.run_for_the_hills(gameboard)
            # Learn:
            if player.shield_count != 0:
                #run this with opponent as parameter next turn, to see if opponent uses lasers while I hold a shield powerup.
                self.opp_lasers = opponent.laser_count
                self.learn_opp_offense = True
            if player.laser_count != 0:
                #run this with opponent as parameter next turn, to see if opponent uses shields or teleports while I hold a laser powerup.
                self.opp_shield_tp = opponent.shield_count + opponent.teleport_count
                self.learn_opp_defense = True
        elif me_in_danger:
            #Survival first, learning second.
            if self.opp_is_aggro_vs_shield:
                if player.shield_count != 0:
                    return Move.SHIELD
            if player.teleport_count != 0:
                return self.run_for_the_hills(gameboard)
            if player.hp == 1:
                if player.shield_count != 0:
                    return Move.SHIELD
            # Learn:
            if player.shield_count != 0:
                #run this with opponent as parameter next turn, to see if opponent uses lasers while I hold a shield powerup.
                self.opp_lasers = opponent.laser_count
                self.learn_opp_offense = True
        elif opp_in_danger:
            #I'm safe, so try to kill opponent.
            #Laser if no shields (present or active).  Else, don't laser, and check next turn for shield presence.  If none, next time laser.
            if self.opp_isnt_defensive_vs_laser:
                if player.laser_count != 0:
                    return Move.LASER
            if opponent.shield_count == 0:
                if player.laser_count != 0:
                    return Move.LASER
            # Learn:
            if player.laser_count != 0:
                #run this with opponent as parameter next turn, to see if opponent uses shields or teleports while I hold a laser powerup.
                self.opp_shield_tp = opponent.shield_count + opponent.teleport_count
                self.learn_opp_defense = True
        #We're both safe and no need for powerups.
        return None
                

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
        # print_debug("checking bullets ({},{})".format(x,y))
        bullets = gameboard.are_bullets_at_tile(x, y)
        # check if the bullet there is headed towards you
        for b in bullets:
            # print_debug("found bullet going {}".format(b.direction))
            if b.direction == direction:
                self.bullet_incoming = b
                break


    def prepare_to_turret_slay(self, gameboard, target_turret, player, opponent, turn, turns_req_uninterrupted):
        '''
        Prepare a turret for turret slaying mode by setting the preparing_slay_mode (holding Move commands).
        preparing_slay_mode is set to None when no more preparations are needed.
        Assumes target_turret is easily killable without moving more than 1 square.
        '''

        # can't slay if facing the wrong way (don't need to modulo since turret is inside grid)
        # moving in the current direction won't be in the way of turret fire (also means turret will be in way of your fire)
        (nx, ny) = self.next_pos((player.x, player.y), player.direction)
        if self.walls[nx][ny] or (nx != target_turret.x and ny != target_turret.y): # turn towards a location in the firing range of turret
            # turn to either get away from wall or towards turret fire
            for d in list(Direction):
                (x,y) = self.next_pos((player.x, player.y), d)
                if x == target_turret.x or y == target_turret.y:
                    self.preparing_slay_mode = self.dir_to_move(player, d)
                    return

        # [fire, cooldown] period starting from 0
        period = target_turret.fire_time + target_turret.cooldown_time;
        # modulo with turn to find current phase
        phase = turn % period
        # for simplicity, assume we are adjacent to where we can fire
        # not the end of the firing cycle, disqualified automatically
        if phase != target_turret.fire_time:
            print_debug("NO SLAY: bad phase")
            self.preparing_slay_mode = Move.NONE
            return

        # cannot slay if about to die
        self.bullet_incoming = None
        self.look_at_cross(gameboard, player.x, player.y, turns_req_uninterrupted, self.cross_no_bullet)
        if self.bullet_incoming:
            print_debug("NO SLAY: bullet incoming ({},{})".format(self.bullet_incoming.x, self.bullet_incoming.y))
            return 

        # dangerous if opponent can get to us
        # NOTE self.dist is from self to the other object, which is only an approximation of the distance
        if self.dist[opponent.x][opponent.y][0] < turns_req_uninterrupted:
            print_debug("NO SLAY: opponent too close")
            return 

        # dangerous if opponent teleports in while turret slaying
        # highly unlikely though, so let's not consider it for now...
        # if opponent.teleport_count:
        #     tele_in = gameboard.teleport_locations
        #     for tele in tele_in:
        #         # distance that either the opponent or their bullet can close + 1 turn for teleport usage
        #         if self.dist[tele[0]][tele[1]][0] + 1 < turns_req_uninterrupted:
        #             print_debug("NO SLAY: opponent can teleport in")
        #             return 

        # finally passed all tests, can enter slay mode
        self.preparing_slay_mode = None



    def turret_slay(self, gameboard, player, opponent):
        # move into position to shoot
        if self.slay_stage == Slay.PREMOVE:
            print_debug("Moving forward")
            self.slay_stage = Slay.PRETURN
            return Move.FORWARD
        # turn to face the turret
        elif self.slay_stage == Slay.PRETURN:
            print_debug("Turning to shoot")
            self.slay_stage = Slay.SHOOT
            for d in list(Direction):
                for i in range(4):
                    x1,y1 = self.next_pos((player.x,player.y),d,n=i+1)
                    if gameboard.is_wall_at_tile(x1,y1): # can't reach turret by going this direction
                        break # go to next direction
                    if gameboard.is_turret_at_tile(x1,y1):  # reached turret without hitting a wall first
                        return self.dir_to_move(player,d)

        # just shoot it
        elif self.slay_stage == Slay.SHOOT:
            print_debug("Shooting")
            # finished slaying turret
            self.slay_stage = Slay.PREMOVE
            print_debug(len(self.last_turret_slay_sq))
            # make sure that when squares are updated, those ones are not added
            self.last_turret_slay_sq = {}
            for k,v in self.turret_slay_sq.items():
                if not (v.x == self.turret_to_slay.x and v.y == self.turret_to_slay.y):
                    self.last_turret_slay_sq[k] = v
            # self.last_turret_slay_sq = {k:v for k,v in self.turret_slay_sq.items() if v.x != self.turret_to_slay.x and v.y != self.turret_to_slay.y}
            print_debug(len(self.last_turret_slay_sq))
            self.turret_to_slay = None
            # get away from turret on the next move by resuming normal behaviour
            return Move.SHOOT


    def is_safe_from_laser(self, player, opponent):
        ''' False iff opponent can hit player no matter what (excepting shield and teleport). '''
        safe_at_curr_pos = self.is_safe_from_one_turretfire(player.x, player.y, opponent.x, opponent.y)
        x1,y1 = self.next_pos((player.x, player.y), player.direction)
        safe_at_next_pos = self.is_safe_from_one_turretfire(x1, y1, opponent.x, opponent.y)
        return safe_at_curr_pos or safe_at_next_pos


    def is_safe_from_one_turretfire(self, x1, y1, tx, ty):
        ''' Also works for Laser usage.  (tx,ty) is source of fire, (x1,y1) is test position. '''
        if tx == x1:
            #checks if you're above/below/right/left of turret, and in range and not blocked by a wall
            #up
            for y in range(ty-1, ty-5, -1):
                if self.walls[tx][y % self.h] == True:
                    break
                if y == y1:
                    #BAD - TURRETFIRE
                    return False
            #down
            for y in range(ty+1, ty+5):
                if self.walls[tx][y % self.h] == True:
                    break
                if y == y1:
                    #BAD - TURRETFIRE
                    return False
        if ty == y1:
            #right
            for x in range(tx-1, tx-5, -1):
                if self.walls[x % self.w][ty] == True:
                    break
                if x == x1:
                    #BAD - TURRETFIRE
                    return False
            #left
            for x in range(tx+1, tx+5):
                if self.walls[x % self.w][ty] == True:
                    break
                if x == x1:
                    #BAD - TURRETFIRE
                    return False
        return True
                    

    def is_safe_from_all_turretfire(self, x1, y1, gameboard):
        ''' Check whether the square at (x1,y1) is safe from turret fire on the next turn. '''
        for turret in gameboard.turrets:
            if turret.is_firing_next_turn:
                # turret about to be destroyed, don't worry about it
                self.bullet_incoming = None
                self.look_at_cross(gameboard, turret.x, turret.y, 1, self.cross_no_bullet)
                if self.bullet_incoming:
                    print_debug("turret at ({},{}) about to die, ignore".format(turret.x, turret.y))
                    continue

                if self.is_safe_from_one_turretfire(x1, y1, turret.x, turret.y) == False:
                    return False
        # safe from all turrets
        return True


    def QA_move(self, gameboard, player, opponent, move):
        ''' Safety-related overrides. '''
        if move == Move.FORWARD:
            (x1,y1) = self.next_pos((player.x, player.y), player.direction)
            #Avoid turretfire.
            if not self.is_safe_from_all_turretfire(x1, y1, gameboard):
                return Move.NONE
            #Avoid bullets
            for bullet in gameboard.bullets:
                if bullet.direction == d_opp[player.direction]:
                    #Bullet right in front of you - RUN!
                    if (bullet.x, bullet.y) == (x1,y1):
                        if player.teleport_count != 0:
                            return self.run_for_the_hills(gameboard)
                        elif player.shield_count != 0:
                            return Move.SHIELD
                        else:
                            return move #nothing to be done; take the damage and go on your merry way.
                    elif self.next_pos((bullet.x, bullet.y), bullet.direction, n=2) == (x1,y1):
                        #Bullet coming at you from 3 squares away - turn away
                        for d in d_perp[bullet.direction]:
                            x2,y2 = self.next_pos((player.x,player.y), d)
                            if self.walls[x2][y2] == False:
                                return self.dir_to_move(player, d)
                if self.next_pos((bullet.x, bullet.y), bullet.direction) == (x1,y1):
                    #Bullet coming at you from 2 squares away - turn away
                    if player.direction not in d_perp[bullet.direction]:
                        for d in d_perp[bullet.direction]:
                            x2,y2 = self.next_pos((player.x,player.y), d)
                            if self.walls[x2][y2] == False:
                                return self.dir_to_move(player, d)
                        else:
                            #Nowhere to turn - RUN!
                            if player.teleport_count != 0:
                                return self.run_for_the_hills(gameboard)
                            elif player.shield_count != 0:
                                return Move.SHIELD
                            else:
                                return move #nothing to be done; take the damage and go on your merry way. 
                    # Bullet on perpendicular path to hit. Just wait. 
                    else:
                        return Move.NONE
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
                            return self.dir_to_move(player, d)
        #If you don't move, check that you won't get injured. 
        elif move in [Move.FACE_LEFT, Move.FACE_RIGHT, Move.FACE_DOWN, Move.FACE_UP, Move.LASER, Move.NONE]:
            x1,y1 = (player.x, player.y)
            if not self.is_safe_from_all_turretfire(x1, y1, gameboard):
                x2,y2 = self.next_pos((x1,y1), player.direction)
                if self.walls[x2][y2] == False:
                    return Move.FORWARD
                elif player.teleport_count != 0:
                    return self.run_for_the_hills(gameboard)
                elif player.shield_count != 0:
                    return Move.SHIELD
                else:
                    return move #nothing to be done; take the damage and go on your merry way.
            #Avoid unavoidable bullets (coming right at you from 1 square)
            for bullet in gameboard.bullets:
                if bullet.direction == d_opp[player.direction]:
                    #Bullet right in front of you - RUN!
                    if (bullet.x, bullet.y) == (x1,y1):
                        if player.teleport_count != 0:
                            return self.run_for_the_hills(gameboard)
                        elif player.shield_count != 0:
                            return Move.SHIELD
                        else:
                            return move #nothing to be done; take the damage and go on your merry way.
        #All seems well.  No overrides. 
        return move


    def calc_destination(self, gameboard, opponent):
        turret_sq, turret_d = self.nearest_turret_slay_sq()
        pu_sq, pu_d = self.nearest_powerup_sq(gameboard)
        print_debug('distances', pu_d, turret_d)
        if pu_d == None and turret_d == None:
            return (opponent.x, opponent.y)
        elif pu_d == None:
            return turret_sq
        elif turret_d == None:
            return pu_sq
        elif turret_d + 1 < pu_d:
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
                            # allow only removal from turret slay squares by keeping track of last turn's squares
                            if self.last_turret_slay_sq != None and (x2,y2) not in self.last_turret_slay_sq:
                                continue
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
                                # allow only removal from turret slay squares by keeping track of last turn's squares
                                if self.last_turret_slay_sq != None and (x2,y2) not in self.last_turret_slay_sq:
                                    continue
                                if self.walls[x2][y2] == False:
                                    self.turret_slay_sq[(x2,y2)] = turret
                        else:
                            break

        self.last_turret_slay_sq = self.turret_slay_sq
            # didn't test on any long range map, so just ignore long range special squares
            # #Can kill any turrets from beyond their shooting range.
            # for d in [Direction.UP, Direction.DOWN]:
            #     x1,y1 = self.next_pos((tx,ty),d)
            #     for i in range(self.h // 2 - 1):
            #         if self.walls[x1][y1] == True:
            #             break
            #         if i >= 4:
            #             self.turret_slay_sq[(x1,y1)] = turret
            #         x1,y1 = self.next_pos((x1,y1),d)
            # for d in [Direction.LEFT, Direction.RIGHT]:
            #     x1,y1 = self.next_pos((tx,ty),d)
            #     for i in range(self.w // 2 - 1):
            #         if self.walls[x1][y1] == True:
            #             break
            #         if i >= 4:
            #             self.turret_slay_sq[(x1,y1)] = turret
            #         x1,y1 = self.next_pos((x1,y1),d)


    def nearest_sq(self, squares):
        # Assumes self.dist calculated.
        if len(squares) == 0:
            return None, None
        closest_sq = min(squares, key=lambda sq: self.dist[sq[0]][sq[1]][0])
        dist = self.dist[closest_sq[0]][closest_sq[1]][0]
        return closest_sq, dist


    def nearest_sq_dict(self, squares):
        # For dictionaries with keys as (x,y):turret
        if len(squares) == 0:
            return None, None
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
        ''' 
        Get coordinates of the square in the opposite direction of
        curr_pos. I.e. moving in direction from prev_pos gets you to
        curr_pos. 
        '''
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
        ''' 
        Magic.  Produces self.dist - a 2D array corresponding to the
        game map, with each cell containint (dist, dirList), where dist
        is the number of turns to get from the player's current position
        to that cell, and dirList is a list of possible final
        orientations / last moves taken to do this in the shortest
        amount of time.

        This array can be used to reconstruct the shortest path from the
        player to any cell, as well as for accurate distance
        measurements. 
        '''
        self.dist = [[(9001,[Direction.DOWN]) for y in range(gameboard.height)] for x in range(gameboard.width)]
        self.calc_distances_propagate(gameboard, {(player.x,player.y) : [player.direction]}, {}, 0)


    def calc_distances_propagate(self, gameboard, squares1, squares2, distance):
        ''' 
        The details:  every square is either 1 turn away or 2 turns
        away, depending on player's current orientation relative to the
        direction of that square.  Thus, we increment distances and
        spread the net of 'reached' squares (keeping track of
        orientation along the shortest paths to deal with above), until
        we've reached all reachable squares.

        squares1, squares2 = {(x,y) : [dList]}, where (x,y) is cell
        coordinate, and dList is the list of directions from which you
        can arrive at this cell along a shortest path (may be multiple). 
        '''
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
        ''' Converts desired Direction enum into a Move enum, accounting for player's orientation. '''
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
