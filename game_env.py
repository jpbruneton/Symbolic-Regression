#  ======================== CMA-Based Symbolic Regressor ========================== #
# Project:          Symbolic regression for physics
# Name:             game_env.py
# Authors:          Jean-Philippe Bruneton
# Date:             2020
# License:          BSD 3-Clause License
# ============================================================================ #

# ================================= PREAMBLE ================================= #
# Packages
from State import State
import config
from Evaluate_fit import Evaluatefit
from AST import AST, Node
import numpy as np
import copy
import random
# =============================== CLASS: Game ================================ #

class Game:

    # ---------------------------------------------------------------------------- #
    # init a game with optional state.
    def __init__(self, voc, state = None):
        self.voc = voc
        self.calculus_mode = voc.calculus_mode
        self.maxL = voc.maximal_size
        if state is None:
            self.stateinit = []
            self.state = State(voc, self.stateinit, self.calculus_mode)
        else:
            self.state = state

    # ---------------------------------------------------------------------------- #
    def scalar_counter(self):
        # says if the current equation is a number (or a vector of numbers!) or not (if counter == 1)
        counter = 0
        for char in self.state.reversepolish:
            # infinity doesnt count as a scalar since we discard such equations from the start; see elsewhere
            if char in self.voc.arity0symbols or char in self.voc.neutral_element or char in self.voc.true_zero_number:
                counter += 1
            elif char in self.voc.arity2symbols:
                counter -= 1
        return counter

    # ------------------------------------------------- #
    def from_rpn_to_critical_info(self):
        # given an equation, returns if it can be terminated or not, the number of vectors (A_vec wedge A_vec is only one vector, etc)
        # and the last two entries type with 0 : scalar, 1 : vector
        can_be_terminated = 0
        for char in self.state.reversepolish:
            if char in self.voc.arity0symbols or char in self.voc.neutral_element or char in self.voc.true_zero_number:
                can_be_terminated += 1
            elif char in self.voc.arity2symbols:
                can_be_terminated -= 1
            else:
                pass

        vec_number = 0 #number of vectors in expression
        stack = []  # this stores the type of the two last entries

        for char in self.state.reversepolish:
            if char in self.voc.terminalsymbol:
                pass

            # arity 0
            elif char in self.voc.arity0symbols:
                if char in self.voc.arity0_vec:
                    vec_number += 1
                    stack.append(1)
                else:
                    stack.append(0)

            # arity 1
            elif char in self.voc.arity1symbols:
                if char in self.voc.norm_number:
                    vec_number -= 1
                    if stack[-1] == 1:
                        stack = stack[:-1] + [0]
                    else:
                        print('fix bug: cant take the norm of a scalar')
                        raise ValueError

                # if function like cos : stack doesnt change but for debug:
                else:
                    if stack[-1] != 0:
                        print('cant take cosine of a vector (no pointwise operations allowed by choice)')
                        raise ValueError

            else:  # arity 2
                lasts = stack[-2:]

                if char in self.voc.divnumber:  # can only be [1, 0] : vector divided by scalar gives a vector:
                    if lasts == [1, 0]:
                        toadd = [1]
                    elif lasts == [0, 0]:
                        toadd = [0]
                    else:
                        print('fix bug: scalar cant be divided by vector; or vector by vector')
                        raise ValueError

                elif char in self.voc.multnumber:
                    if lasts == [0, 0]:
                        toadd = [0]
                    elif lasts == [0, 1] or lasts == [1, 0]:
                        toadd = [1]
                    else:
                        print('fix bug: vectors cannot be multiplied')
                        raise ValueError

                elif char in self.voc.plusnumber or char in self.voc.minusnumber:
                    if lasts == [0,0]:
                        toadd = [0]
                    elif lasts == [0,1] or lasts == [1,0]:
                        print('fix bug: scalars cant be added to a vector')
                        raise ValueError
                    else: # add two vectors : reduce n_vec one unit
                        toadd = [1]
                        vec_number -=1

                elif char in self.voc.power_number:
                    if lasts == [0, 0]:
                        toadd = [0]
                    else:
                        print('bug fixing : power not authorized here')
                        raise ValueError

                elif char in self.voc.wedge_number:
                    vec_number -= 1
                    if lasts == [1, 1]:
                        toadd = [1]
                    else:
                        print('bug fix : wedge not allowed')
                        raise ValueError

                elif char in self.voc.dot_number:
                    vec_number -= 2
                    if lasts == [1, 1]:
                        toadd = [0]
                    else:
                        print('bug : dot product not allowed')
                        raise ValueError

                # update stack
                stack = stack[:-2] + toadd

        return can_be_terminated, vec_number, stack


    # ---------------------------------------------------------------------------- #
    def allowedmoves_vectorial(self):
        # determines which character can be added to the rpn in vectorial mode, under the constraint that the equation
        # must eventually terminate with a maximal size
        current_state_size = len(self.state.reversepolish)
        space_left = self.maxL - current_state_size
        current_A_number = sum([1 for x in self.state.reversepolish if x == self.voc.pure_numbers[0]])
        current_A_number += sum([3 for x in self.state.reversepolish if x == self.voc.pure_numbers[1]]) #this assumes 3D vectors

        # init : we go upward in the tree so we must start with a scalar
        if current_state_size == 0:
            allowedchars = self.voc.arity0symbols #start either with a vec or a scalar

        else:
            # check if already terminated
            if self.state.reversepolish[-1] in self.voc.terminalsymbol or space_left == 0:
                allowedchars = []
            else:
                can_be_terminated, vec_number, stack = self.from_rpn_to_critical_info()
                info = [self.state.formulas, can_be_terminated, vec_number, stack]

                if can_be_terminated == 0:
                    print('bug : should not happen at all here 1', info)
                    raise ValueError

                # First case : one character left -----------
                if space_left == 1:
                    if can_be_terminated == 1: # must terminate
                        allowedchars = self.voc.terminalsymbol
                        if vec_number !=1:
                            print('this shd not happen otherwise we get a non vectorial expression 2', info)
                            raise ValueError

                    elif can_be_terminated == 2:
                        if vec_number == 1: # two numbers one vec one scalar
                            if stack[-2:] == [0, 1]:
                                allowedchars = self.voc.multnumber
                            elif stack[-2:] == [1, 0]:
                                allowedchars = self.voc.multnumber + self.voc.divnumber
                            else:
                                print('debug shd not happen 3', info)
                                raise ValueError

                        elif vec_number ==2:
                            if stack[-2:] == [1, 1]:  # A wedge A, A+A or A -A
                                allowedchars = self.voc.wedge_number + self.voc.plusnumber + self.voc.minusnumber

                    else:
                        print('bug : cant terminate 4', info)
                        raise ValueError

                # Case space left is 2 -------------
                elif space_left == 2 :

                    if can_be_terminated == 1:
                        if vec_number == 0: #must add a vector
                            allowedchars = self.voc.arity0_vec
                        elif vec_number==1:
                            allowedchars = self.voc.terminalsymbol
                            allowedchars += self.voc.arity0symbols
                        else:
                            print('must not happen 5', info)
                            raise ValueError

                    elif can_be_terminated == 2: #operator required
                        if vec_number == 0:
                            print('must not happen 6', info)
                            raise ValueError

                        elif vec_number == 1:
                            if stack[-2:] == [0,1]:
                                allowedchars = self.voc.multnumber
                            elif stack[-2:] == [1, 0]:
                                allowedchars = self.voc.multnumber + self.voc.divnumber
                            else:
                                print('bug fixing 7', info)
                                raise ValueError

                        elif vec_number == 2: #op required and decrease vec number, thus:
                            allowedchars = self.voc.plusnumber + self.voc.minusnumber + self.voc.wedge_number

                        else:
                            print('bug fixing 8', info)
                            raise ValueError

                    elif can_be_terminated == 3: #two operators required
                        if vec_number == 0:
                            print('must not happen 9', info)
                            raise ValueError
                        elif vec_number == 1:
                            if stack[-3:] == [0,0,1]:
                                allowedchars = self.voc.multnumber
                            elif stack == [0,1,0]:
                                allowedchars = self.voc.multnumber + self.voc.divnumber
                            elif stack == [1,0,0]:
                                allowedchars = self.voc.arity2novec
                            else:
                                print('bugfixing10', info)
                                raise ValueError
                        elif vec_number == 2: #2 op required and minus one vector:
                            if stack[-3:] == [0,1,1]:
                                allowedchars = self.voc.plusnumber + self.voc.minusnumber + self.voc.wedge_number
                            elif stack == [1,0,1]:
                                allowedchars = self.voc.multnumber
                            elif stack == [1,1,0]:
                                allowedchars = self.voc.multnumber + self.voc.divnumber
                            else:
                                print('bugfixing11', info)
                                raise ValueError

                        elif vec_number == 3: # case stack 1 1 1
                            allowedchars = self.voc.dot_number + self.voc.plusnumber + self.voc.minusnumber + self.voc.wedge_number
                        else:
                            print('bugfixing11', info)
                            raise ValueError

                # General case-------------
                elif space_left >= 3:
                    t = can_be_terminated - 1  # this equals to the number of operators required
                    nu = vec_number - 1  # number of extra vectors : if >=1 : must reduce the number of vectors
                    p = space_left
                    allowedchars = []
                    if nu == 0 and t == 0:
                        allowedchars = self.voc.terminalsymbol

                    if p < t:
                        print('impossible to terminate must not happen 12', info)
                        raise ValueError

                    elif p == t: # t operators required in t space left : only operators allowed here
                        if nu == -1:
                            print('impossible to terminate with a vec expression  13: shd never happen', info)
                            raise ValueError
                        elif nu >= 0:
                            lasts = stack[-2:]
                            if lasts == [0,0]:
                                allowedchars += self.voc.arity2novec
                            elif lasts == [0,1]:
                                allowedchars += self.voc.multnumber
                            elif lasts == [1, 0]:
                                allowedchars += self.voc.multnumber + self.voc.divnumber
                            elif lasts == [1,1] and nu <=1:
                                allowedchars += self.voc.plusnumber + self.voc.minusnumber + self.voc.wedge_number
                            else:
                                allowedchars += self.voc.dot_number + self.voc.plusnumber + self.voc.minusnumber + self.voc.wedge_number

                    elif p == t+1:
                        # cant add a scalar, but functions,and norm
                        if stack[-1] == 0 and self.getnumberoffunctions() < config.MAX_DEPTH:
                            allowedchars += self.voc.arity1_novec
                        elif stack[-1] == 1 and nu >=1 and self.getnumberoffunctions() < config.MAX_DEPTH:
                            allowedchars += self.voc.norm_number

                        lasts = stack[-2:]
                        if lasts == [0, 0]:
                            allowedchars += self.voc.arity2novec
                        if lasts == [0, 1]:
                            allowedchars += self.voc.multnumber
                        if lasts == [1, 0]:
                            allowedchars += self.voc.multnumber + self.voc.divnumber
                        if lasts == [1, 1]:
                            allowedchars += self.voc.plusnumber + self.voc.minusnumber + self.voc.wedge_number
                        if lasts == [1,1] and nu >=2 and self.getnumberoffunctions() < config.MAX_DEPTH:
                            allowedchars+= self.voc.dot_number

                    else :
                        if nu==-1:
                            allowedchars  += self.voc.arity0_vec
                        elif nu >= 0:
                            allowedchars += self.voc.arity0symbols
                            if stack[-1] == 0 and self.getnumberoffunctions() < config.MAX_DEPTH:
                                allowedchars+= self.voc.arity1_novec
                            if stack[-1] == 1 and nu>=1 and self.getnumberoffunctions() < config.MAX_DEPTH:
                                allowedchars += self.voc.norm_number
                            if stack[-1] == 1 and nu == 1 and self.getnumberoffunctions() < config.MAX_DEPTH and p-(t+1) >=3:
                                allowedchars += self.voc.norm_number

                            lasts = stack[-2:]
                            if lasts == [0, 0]:
                                allowedchars += self.voc.arity2novec
                            if lasts == [0, 1]:
                                allowedchars += self.voc.multnumber
                            if lasts == [1, 0]:
                                allowedchars += self.voc.multnumber + self.voc.divnumber
                            if lasts == [1,1]:
                                allowedchars += self.voc.dot_number + self.voc.plusnumber + self.voc.minusnumber + self.voc.wedge_number

                    # option that counter the tendency to create too long expresions : enforce terminal state now and then:
                    if True:
                        if nu==0 and t==0:
                            if random.random() < config.force_terminal:
                                allowedchars = self.voc.terminalsymbol
                            else:
                                pass

        return allowedchars

    # ---------------------------------------------------------------------------- #
    def allowedmoves_novectors(self):
        # determines which character can be added to the rpn in scalar only mode, quite similar though simpler

        current_state_size = len(self.state.reversepolish)
        space_left = self.maxL - current_state_size

        #init : we go upward so we must start with a scalar
        if current_state_size == 0:
            allowedchars = self.voc.arity0symbols

        else:
            #check if already terminated
            if self.state.reversepolish[-1] in self.voc.terminalsymbol or space_left == 0:
                allowedchars = []

            else:
                scalarcount = self.scalar_counter()
                current_A_number =  sum([1 for x in self.state.reversepolish if x in self.voc.pure_numbers])

                # check if we must terminate
                if space_left == 1:
                    if scalarcount == 1 : #expression is a scalar -> ok, terminate
                        allowedchars = self.voc.terminalsymbol

                    else: # scalarcount cant be greater than 2 at that point thanks to the code afterwards:

                        # take care of power specifics (option)
                        if config.only_scalar_in_power:
                            if self.state.reversepolish[-1] in self.voc.pure_numbers:
                                allowedchars = self.voc.arity2symbols
                            else:
                                allowedchars = self.voc.arity2symbols_no_power

                        else:
                            allowedchars = self.voc.arity2symbols

                # case space left >=2
                else:
                    if scalarcount == 1:
                        allowedchars = self.voc.terminalsymbol

                        if space_left >= scalarcount + 1:
                            if current_A_number < config.max_A_number:
                                allowedchars += self.voc.arity0symbols
                            else:
                                allowedchars += self.voc.arity0symbols_var_and_tar

                        if space_left >= scalarcount:
                            if self.getnumberoffunctions() < config.MAX_DEPTH :
                                allowedchars += self.voc.arity1symbols


                    if scalarcount >= 2:
                        #take care of power specifics
                        if config.only_scalar_in_power :
                            if self.state.reversepolish[-1] in self.voc.pure_numbers:
                                allowedchars = self.voc.arity2symbols
                            else:
                                allowedchars = self.voc.arity2symbols_no_power

                        else:
                            allowedchars = self.voc.arity2symbols

                        if space_left >= scalarcount+1:
                            if current_A_number < config.max_A_number:
                                allowedchars += self.voc.arity0symbols
                            else:
                                allowedchars += self.voc.arity0symbols_var_and_tar

                        if space_left >= scalarcount:
                            # also avoid stuff like exp(exp(exp(exp(sin(x))))
                            if self.getnumberoffunctions() < config.MAX_DEPTH :
                                allowedchars += self.voc.arity1symbols

        return allowedchars

    # ---------------------------------------------------------------------------- #
    def getnumberoffunctions(self, state = None):
        # returns the number of *nested* functions
        # use the same stack as everywhere else but only keep in the stack the number of nested functions encountered so far
        stack = []
        if state is None:
            state = self.state
        for number in state.reversepolish:
            if number in self.voc.arity0symbols or number in self.voc.true_zero_number or number in self.voc.neutral_element:
                stack += [0]

            elif number in self.voc.arity1symbols:
                if len(stack) == 1:
                    stack = [stack[0] +1]
                else:
                    stack = stack[0:-1] + [stack[-1] + 1]

            elif number in self.voc.arity2symbols:
                stack = stack[0:-2] + [max(stack[-1], stack[-2])]

        if len(stack)>0:
            return stack[-1]
        else:
            return 0
    #---------------------------------------------------------------------- #
    def nextstate(self, nextchar):
        ''' Given a next char, produce nextstate WITHOUT ACTUALLY UPDATING THE STATE (it is a virtual move)'''
        nextstate = copy.deepcopy(self.state.reversepolish)
        nextstate.append(nextchar)
        return State(self.voc, nextstate, self.calculus_mode)

    # ---------------------------------------------------------------------------- #
    def takestep(self, nextchar):
        ''' actually take the action = update state to nextstate '''
        self.state = self.nextstate(nextchar)

    # ---------------------------------------------------------------------------- #
    def isterminal(self):
        if self.calculus_mode == 'scalar':
            if self.allowedmoves_novectors() == []:
                return 1
            else:
                return 0
        if self.calculus_mode == 'vectorial':
            if self.allowedmoves_vectorial() == []:
                return 1
            else:
                return 0

    # ---------------------------------------------------------------------------- #
    def convert_to_ast(self):
        # convert a rpn state into an AST

        # only possible if the expression is a scalar, thus: for debug
        if self.scalar_counter() !=1:
            print(self.voc.numbers_to_formula_dict)
            print(self.state.reversepolish)
            print(self.state.formulas)
            print('cant convert a non scalar expression to AST')
            raise ValueError

        stack_of_nodes = []
        count = 1
        for number in self.state.reversepolish:
            #init :
            if stack_of_nodes == []:
                ast = AST(number)
                stack_of_nodes += [ast.onebottomnode]

            else:
                if number in self.voc.arity0symbols or number in self.voc.true_zero_number or number in self.voc.neutral_element:
                    newnode = Node(number, 0, None, None ,count)
                    stack_of_nodes += [newnode]

                elif number in self.voc.arity1symbols:
                    lastnode = stack_of_nodes[-1]
                    newnode = Node(number, 1, [lastnode], None ,count)
                    lastnode.parent = newnode
                    if len(stack_of_nodes) == 1:
                        stack_of_nodes = [newnode]
                    if len(stack_of_nodes) >= 2:
                        stack_of_nodes = stack_of_nodes[:-1] + [newnode]

                elif number in self.voc.arity2symbols:
                    newnode = Node(number, 2, [stack_of_nodes[-2], stack_of_nodes[-1]], None, count)
                    stack_of_nodes[-2].parent = newnode
                    stack_of_nodes[-1].parent = newnode
                    stack_of_nodes =  stack_of_nodes[:-2] + [newnode]
            count+=1

        # terminate
        ast.topnode = stack_of_nodes[0]
        return ast

    # ------------------------
    def get_features(self):
        # returns the numbers used to populate the Quality-Diversity Grid

        if self.state.reversepolish[-1] in self.voc.terminalsymbol:
            L = len(self.state.reversepolish) - 1
        else:
            L = len(self.state.reversepolish)

        function_number = 0
        mytargetnumber = 0
        firstder_number = 0
        depth = self.getnumberoffunctions()
        varnumber = 0
        if self.calculus_mode == 'scalar':
            for char in self.state.reversepolish:
                if char in self.voc.arity1symbols:
                    function_number += 1
                elif char in self.voc.targetfunction_number:
                    mytargetnumber += 1
                elif char in self.voc.first_der_number:
                    firstder_number += 1
                elif char in self.voc.var_numbers:
                    varnumber += 1
            return L, function_number, mytargetnumber, firstder_number, depth, varnumber

        else:
            dotnumber = 0
            normnumber = 0
            crossnumber =0
            for char in self.state.reversepolish:
                if char in self.voc.arity1_novec:
                    function_number += 1
                elif char in self.voc.targetfunction_number:
                    mytargetnumber += 1
                elif char in self.voc.first_der_number:
                    firstder_number += 1
                elif char in self.voc.wedge_number:
                    crossnumber += 1
                elif char in self.voc.norm_number:
                    normnumber += 1
                elif char in self.voc.dot_number:
                    dotnumber += 1
                elif char in self.voc.var_numbers:
                    varnumber += 1
            return L, function_number, mytargetnumber, firstder_number, depth, varnumber, dotnumber, normnumber, crossnumber

# =================  END class Game =========================== #


# ---------------------------------------------------------------------------- #
# create random eqs (+ simplify in option)

def randomeqs(voc):
    game = Game(voc, state=None)
    np.random.seed() #is this required? seems so in mp.pool
    while game.isterminal() == 0:
        if voc.calculus_mode == 'scalar':
            nextchar = np.random.choice(game.allowedmoves_novectors())
            game.takestep(nextchar)
        else:
            allowed_moves = game.allowedmoves_vectorial()
            nextchar = np.random.choice(allowed_moves)
            game.takestep(nextchar)

    if config.use_simplif:
        simplestate = simplif_eq(voc, game.state)
        simplegame = Game(voc, simplestate)
        return simplegame

    else:
        return game

# ---------------------------------------------------------
def simplif_eq(voc, state, calculus_mode):
    count = 0
    change = 1
    while change == 1:
        # simplify the equations, terminate when no change occur anymore or maxcount reached
        # (only if simplif rules are circular hence flawed)
        change, rpn = state.one_simplif()
        state = State(voc, rpn, calculus_mode)
        count += 1
        if count > 1000:
            change = 0
    return state

# ---------------------------------------------------------------------------- #
# takes a non maximal size and completes it with random + simplify it with my rules
def complete_eq_with_random(voc, state, calculus_mode):
    if state.reversepolish[-1] == voc.terminalsymbol:
        newstate = State(voc, state.reversepolish[:-1], calculus_mode)
    else :
        newstate = copy.deepcopy(state)
    game = Game(voc, newstate)
    while game.isterminal() == 0:
        if voc.calculus_mode == 'scalar':
            nextchar = np.random.choice(game.allowedmoves_novectors())
            game.takestep(nextchar)
        else:
            nextchar = np.random.choice(game.allowedmoves_vectorial())
            game.takestep(nextchar)
    if config.use_simplif:
        simplestate = simplif_eq(voc, game.state)
        return simplestate
    else:
        return game.state

# -------------------------------------------------------------------------- #
def game_evaluate(rpn, formulas, voc, train_targets, diffmode, u, look_for):
    # infinite symbol only comes from simplification if used
        if voc.infinite_number[0] in rpn:
            return 0, [], 100000000
        else:
            myfit = Evaluatefit(formulas, voc, train_targets, diffmode, u, look_for)
        return myfit.evaluate()