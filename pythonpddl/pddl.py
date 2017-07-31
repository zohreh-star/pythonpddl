#!/usr/bin/python
# -*- coding: utf-8 -*-

#
# Copyright 2017 Erez Karpas
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
#



from antlr4 import *
from pddlpy import pddlLexer
from pddlpy import pddlParser


import itertools
import sys



class TypedArg:
    """ represents an argument (possibly typed)"""
    def __init__(self,arg_name, arg_type = None):
        self.arg_name = arg_name
        self.arg_type = arg_type

    def asPDDL(self):
        if self.arg_type is None:
            return self.arg_name
        else:
            return self.arg_name + " - " + self.arg_type

class TypedArgList:
    """ represents a list of arguments (possibly with types)"""
    def __init__(self, args):
        self.args = args
#        self.complete_missing_types()
#
#    def complete_missing_types(self):
#        last_type = None
#        for arg in reversed(self.args):
#            if arg.arg_type is not None:
#                last_type = arg.arg_type
#            else:
#                arg.arg_type = last_type
   
    def asPDDL(self):
        return " ".join(map(lambda x: x.asPDDL(), self.args))


def parseTypeVariableList(tvl):
    args = []

    arg_name = ""
    arg_type = "<NONE>"
    
    for arg in tvl.singleTypeVarList():
        arg_type = arg.r_type().getText()
        for arg_context in arg.VARIABLE():
            arg_name = arg_context.getText()
            args.append(TypedArg(arg_name, arg_type))
    for arg_context in tvl.VARIABLE():
        arg_name = arg_context.getText()
        args.append(TypedArg(arg_name))
        
    return TypedArgList(args)


def parseTypeNameList(tnl):
    args = []

    arg_name = ""
    arg_type = "<NONE>"
    
    for arg in tnl.singleTypeNameList():
        arg_type = arg.r_type().getText()
        for arg_context in arg.name():
            arg_name = arg_context.getText()
            args.append(TypedArg(arg_name, arg_type))
    for arg_context in tnl.name():
        arg_name = arg_context.getText()
        args.append(TypedArg(arg_name))
        
    return TypedArgList(args)

class Function:
    """ represents a function"""
    def __init__(self, name, args):
        self.name = name
        self.args = args

    def asPDDL(self):
        return "(" + self.name + " " + self.args.asPDDL() + ")"

class Predicate:
    """ represents a predicate"""
    def __init__(self, name, args):
        self.name = name
        self.args = args

    def asPDDL(self):
        return "(" + self.name + " " + self.args.asPDDL() + ")"

def parsePredicate(pred):
    return Predicate(pred.predicate().name().getText(), parseTypeVariableList(pred.typedVariableList()))


class Formula:
    """ represented a goal description (atom / negated atom / and / or)"""
    def __init__(self, subgoals, op = None):
        self.subgoals = subgoals
        self.op = op
   
    def get_predicates(self, positive):
        """ returns positive or negative predicates in this goal description"""
        if self.op is None and positive:
            assert len(self.subgoals) == 1
            return [self.subgoals[0]]
        elif self.op == "not" and not positive:
            assert len(self.subgoals) == 1
            return [self.subgoals[0]]
        elif self.op == "and":
            l = []
            for s in self.subgoals:
                l = l + s.get_predicates(positive)
            return l
        elif self.op == "or":
            raise Exception("Don't know how to handle disjunctive condition " + str(self.subgoals))
        return []

    def asPDDL(self):
        if self.op is None:
            assert len(self.subgoals) == 1
            return self.subgoals[0].asPDDL()
        elif self.op == "not":
            assert len(self.subgoals) == 1
            return "(not " + self.subgoals[0].asPDDL() + ")"
        elif self.op == "and":
            return "(" + self.op + " " + " ".join(map(lambda x: x.asPDDL(), self.subgoals)) + ")"
        elif self.op == "or":
            raise Exception("Don't know how to handle disjunctive condition " + str(self.subgoals))
        else:
            raise Exception("Don't know how to handle op " + self.op)

def parseGoalDescription(gd):
    """ parses a goal description. Returns a Formula"""
    if gd.atomicTermFormula() is not None:
        name = gd.atomicTermFormula().predicate().name().getText()
        terms = []
        for t in gd.atomicTermFormula().term():
            if t.VARIABLE() is not None:
                terms.append(TypedArg(t.VARIABLE().getText()))
            elif t.name() is not None:
                terms.append(TypedArg(t.name().getText()))
            else:
                raise Exception("Can't handle term " + gd.getText())

        op = None
        if gd.getChildCount() > 1:
            # This hack is meant to take care of negative effects
            op = gd.getChild(1).getText()
        return Formula([Predicate(name, TypedArgList(terms))], op)
    elif gd.fComp() is not None:
        raise Exception("unhandled fcomp condition " + gd.getText())
    else:
        op = gd.getChild(1).getText()
        preds = []
        for p in gd.goalDesc():
            preds.append(parseGoalDescription(p))
        return Formula(preds, op)

class TimedFormula:
    """ represents a timed goal description"""
    def __init__(self, timespecifier, gd):
        self.timespecifier = timespecifier
        self.gd = gd

    def asPDDL(self):
        if self.timespecifier == "start":
            return "(at start " + self.gd.asPDDL() + ")"
        elif self.timespecifier == "end":
            return "(at end " + self.gd.asPDDL() + ")"
        elif self.timespecifier == "all":
            return "(over all " + self.gd.asPDDL() + ")"

def parseTimedGoalDescription(timedGD):
    gd = parseGoalDescription(timedGD.goalDesc())
    timespecifier = None
    if timedGD.interval() is not None:
        timespecifier = timedGD.interval().getText()
    elif timedGD.timeSpecifier() is not None:
        timespecifier = timedGD.timeSpecifier().getText()
    return TimedFormula(timespecifier, gd)



class PrefTimedGoalDescription:
    """ represents a timed goal description, possibly with a preference"""
    def __init__(self, timedgd, prefname = None):
        self.timedgd = timedgd
        self.prefname = prefname
        assert self.prefname is not None

    def asPDDL(self):
        return "(preference " + self.prefname + " " + self.timedgd.asPDDL() + ")"

def parsePrefTimedGoalDescription(prefTimedGD):
    timedGD = parseTimedGoalDescription(prefTimedGD.timedGD())
    name = prefTimedGD.name()
    if name is not None:
        raise Exception("Can't handle preferences " + prefTimedGD.getText())
        return PrefTimedGoalDescription(name, timedGD)
    else:
        return timedGD


def parseCEffect(ceff):
    if ceff.condEffect() is not None:
        raise Exception("Can't handle conditional effect " + ceff.getText())
    elif ceff.typedVariableList() is not None:
        raise Exception("Can't handle quantified effect " + ceff.getText())
    else:
        assert ceff.pEffect() is not None
        return parseGoalDescription(ceff.pEffect())        

def parseTimedEffect(timedEffect):
    timespecifier = timedEffect.timeSpecifier().getText()
    if timedEffect.cEffect() is not None:
        ceff = parseCEffect(timedEffect.cEffect())
        return TimedFormula(timespecifier, ceff)
    else:
        raise Exception("Don't know how to handle effect " + timedEffect.getText())

def parseDaEffect(daEffect):
    if daEffect.timedEffect() is not None:
        te = parseTimedEffect(daEffect.timedEffect())
        return [te]
    else:
        op = daEffect.getChild(1).getText()
        assert op == 'and'
        effs = []
        for p in daEffect.daEffect():
            effs = effs + parseDaEffect(p)
        return effs


class Action:
    """ represents a (non-durative) action"""
    def __init__(self, name, parameters, pre, eff):
        self.name = name
        self.parameters = parameters
        self.pre = pre                  #precondition formula
        self.eff = eff                  #list of effects

    def get_pre(self, positive):        
        return self.pre.get_predicates(positive)

    def get_eff(self, positive):
        l = []
        for x in self.eff:
            l = l + x.get_predicates(positive)
        return l
            

    def asPDDL(self):
        ret = ""
        ret = ret + "(:action " + self.name + "\n"
        ret = ret + "\t:parameters (" + self.parameters.asPDDL() + ")\n"
        ret = ret + "\t:precondition " + self.pre.asPDDL() + "\n"
        ret = ret + "\t:effect (and "  + " ".join(map(lambda x: x.asPDDL(), self.eff)) + ")\n"
        ret = ret + ")"
        return ret

def parseAction(act):
    name = act.actionSymbol().getText()
    parameters = parseTypeVariableList(act.typedVariableList())
    
    body = act.actionDefBody()

    action_cond = []
    pre = parseGoalDescription(body.precondition().goalDesc())

    effs = list(map(lambda x: parseCEffect(x), body.effect().cEffect()))
            
    return Action(name, parameters, pre, effs)


class DurativeAction:
    """ represents a durative action"""
    def __init__(self, name, parameters, duration_lb, duration_ub, cond, eff):
        self.name = name
        self.parameters = parameters
        self.duration_lb = duration_lb
        self.duration_ub = duration_ub
        self.cond = cond               # list of conditions
        self.eff = eff                 # list of effects

    def get_cond(self, timespecifier, positive):
        l = []
        for x in self.cond:
            if x.timespecifier == timespecifier:
                l = l + x.gd.get_predicates(positive)
        return l

    def get_eff(self, timespecifier, positive):
        l = []
        for x in self.eff:
            if x.timespecifier == timespecifier:
                l = l + x.gd.get_predicates(positive)
        return l
            

    def asPDDL(self):
        ret = ""
        ret = ret + "(:durative-action " + self.name + "\n"
        ret = ret + "\t:parameters (" + self.parameters.asPDDL() + ")\n"
        ret = ret + "\t:duration "
        if self.duration_lb == self.duration_ub:
            ret = ret + "(= ?duration " + self.duration_lb.asPDDL() + ")\n"
        else:
            ret = ret + "(and (<= ?duration " + self.duration_ub.asPDDL() + ") (>= ?duration " + self.duration_lb.asPDDL() + "))\n"
        ret = ret + "\t:condition (and "  + " ".join(map(lambda x: x.asPDDL(), self.cond)) + ")\n"
        ret = ret + "\t:effect (and "  + " ".join(map(lambda x: x.asPDDL(), self.eff)) + ")\n"
        ret = ret + ")"
        return ret


class FHead:
    """ represents a functional symbol and terms, e.g.,  (f a b c)"""
    def __init__(self, name, args):
        self.name = name
        self.args = args

    def asPDDL(self):
        return "(" + self.name + " " + self.args.asPDDL() + ")"

def parseFHead(fhead):
    terms = []
    for t in fhead.term():
        if t.VARIABLE() is not None:
            terms.append(TypedArg(t.VARIABLE().getText()))
        elif t.name() is not None:
            terms.append(TypedArg(t.name().getText()))
        else:
            raise Exception("Can't handle term " + fhead.getText())
    return FHead(fhead.functionSymbol().name().getText(), TypedArgList(terms))

class ConstantNumber:
    """ represents a constant number"""
    def __init__(self, val):
        self.val = val

    def asPDDL(self):
        return str(self.val)

    def __eq__(self, other):
        return isinstance(other, ConstantNumber) and self.val == other.val

def parseConstantNumber(number):
    return ConstantNumber(float(number.getText()))


class FExpression:
    """ represents a functional / numeric expression"""
    def __init__(self, op, fexp1, fexp2 = None):
        self.op = op
        self.fexp1 = fexp1
        self.fexp2 = fexp2

    def asPDDL(self):
        if self.op == '-':
            assert self.fexp2 is None
            return "(-" + self.fexp1.asPDDL() + ")"
        else:
            return "(" + self.op + " " + self.fexp1.asPDDL() + " " + self.fexp2.asPDDL() + ")"

def parseFExp(fexp):
    if fexp.NUMBER() is not None:
        return parseConstantNumber(fexp.NUMBER())
    elif fexp.fHead() is not None:
        return parseFHead(fexp.fHead())
    else:
        op = None
        fexp1 = parseFExp(fexp.fExp())
        fexp2 = None
        if fexp.binaryOp() is not None:
            op = fexp.binaryOp().getText()
            fexp2 = parseFExp(fexp.fExp2().fExp())
        else:
            op = "-"
        return FExpression(op, fexp1, fexp2)


def parseSimpleDurationConstraint(sdc):
    op = sdc.durOp().getText()
    

    if sdc.durValue().NUMBER() is not None:
        val = parseConstantNumber(sdc.durValue().NUMBER())
    elif sdc.durValue().fExp() is not None:
        val = parseFExp(sdc.durValue().fExp())
    return (op, val)

def parseDurativeAction(da):
    name = da.actionSymbol().getText()
    parameters = parseTypeVariableList(da.typedVariableList())
    
    body = da.daDefBody()

    duration = body.durationConstraint().simpleDurationConstraint()
    duration_lb = None
    duration_ub = None
    if duration is not None:
        if len(duration) == 1:
            d = parseSimpleDurationConstraint(duration[0])
            assert d[0] == '='
            duration_lb = d[1]
            duration_ub = d[1]
        else:
            assert len(duration) == 2
            d1 = parseSimpleDurationConstraint(duration[0])
            d2 = parseSimpleDurationConstraint(duration[1])
            if d1[0] == '<=':
                assert d2[0] == '>='
                duration_lb = d2[1]
                duration_ub = d1[1]
            elif d1[0] == '>=':
                assert d2[0] == '<='
                duration_lb = d1[1]
                duration_ub = d2[1]
            else:
                raise Exception("Can't parse duration " + duration.getText())
    
    

    action_cond = []
    cond = body.daGD()
    if cond.typedVariableList() is not None:
        raise Exception("Can't handle forall " + cond.getText())
    elif cond.prefTimedGD() is not None:
        action_cond.append(parsePrefTimedGoalDescription(cond.prefTimedGD()))
    elif cond.daGD() is not None:
        for x in cond.daGD():
            action_cond.append(parsePrefTimedGoalDescription(x.prefTimedGD()))

    effs = parseDaEffect(body.daEffect())
            
    return DurativeAction(name, parameters, duration_lb, duration_ub, action_cond, effs)


class Domain:
    """ represents a PDDL domain"""
    def __init__(self, name, reqs, types, constants, predicates, functions, actions, durative_actions):
        self.name = name
        self.reqs = reqs
        self.types = types
        self.constants = constants
        self.predicates = predicates
        self.functions = functions
        self.actions = actions
        self.durative_actions = durative_actions

    def asPDDL(self):
        ret = ""
        ret = ret + "(define (domain " + self.name + ")\n"
        ret = ret + "\t(:requirements " + " ".join(self.reqs) + ")\n"
        ret = ret + "\t(:types " + self.types.asPDDL() + ")\n"
        ret = ret + "\t(:constants " + self.constants.asPDDL() + ")\n"
        
        if len(self.functions) > 0:
            ret = ret + "\t(:functions\n"
            for func in self.functions:
                ret = ret + "\t\t" + func.asPDDL() + "\n"
            ret = ret + "\t)\n"
        
        if len(self.predicates) > 0:
            ret = ret + "\t(:predicates\n"
            for pred in self.predicates:
                ret = ret + "\t\t" + pred.asPDDL() + "\n"
            ret = ret + "\t)\n"


        for a in self.actions:   
            ret = ret + a.asPDDL() + "\n"


        for da in self.durative_actions:   
            ret = ret + da.asPDDL() + "\n"

        ret = ret + ")"
        return ret
        

def parseDomain(domain):
    # Get name
    domainname = domain.domainName().name().getText()

    reqs = []
    for r in domain.requireDef().REQUIRE_KEY():
        reqs.append(r.getText())


    # Get types
    if domain.typesDef() is not None:
        types = parseTypeNameList(domain.typesDef().typedNameList())
    else:
        types = TypedArgList([])

    # Get constants
    if domain.constantsDef() is not None:
        constants = parseTypeNameList(domain.constantsDef().typedNameList())
    else:
        constants = TypedArgList([])

    functions = []
    if domain.functionsDef() is not None:
        for func in domain.functionsDef().functionList().atomicFunctionSkeleton():
            functions.append(Function(func.functionSymbol().name().getText(), parseTypeVariableList(func.typedVariableList())))

    predicates = []
    if domain.predicatesDef() is not None:
        for pred in domain.predicatesDef().atomicFormulaSkeleton():
            predicates.append(Predicate(pred.predicate().name().getText(), parseTypeVariableList(pred.typedVariableList())))

    durative_actions = []
    actions = []
    for action in domain.structureDef():
        if action.actionDef() is not None:
            actions.append(parseAction(action.actionDef()))
        elif action.durativeActionDef() is not None:
            durative_actions.append(parseDurativeAction(action.durativeActionDef()))
    
    d = Domain(domainname, reqs, types, constants, predicates, functions, actions, durative_actions)
    return d
        
    








class Problem:
    """ represents a PDDL problem"""
    def __init__(self, name, domainname, objects, initialstate, goal):
        self.name = name
        self.domainname = domainname
        self.objects = objects
        self.initialstate = initialstate
        self.goal = goal

    def asPDDL(self):
        ret = ""
        ret = ret + "(define (problem " + self.name + ")\n"
        ret = ret + "\t(:domain " + self.domainname + ")\n"
        ret = ret + "\t(:objects " + self.objects.asPDDL() + ")\n"
        ret = ret + "\t(:init \n"
        for initel in self.initialstate:
            ret = ret + "\t\t" + initel.asPDDL() + "\n"
        ret = ret + "\t)\n"
        ret = ret + "\t(:goal " +  self.goal.asPDDL() + ")\n"

        ret = ret + ")"
        return ret
        

def parseInitStateElement(initel):
    if initel.nameLiteral() is not None:
        name = initel.nameLiteral().atomicNameFormula().predicate().name().getText()
        terms = []
        for t in initel.nameLiteral().atomicNameFormula().name():
            terms.append(TypedArg(t.NAME().getText()))

        op = None
        if initel.getChildCount() > 1:
            # This hack is meant to take care of negative effects
            op = initel.getChild(1).getText()       
        return Formula([Predicate(name, TypedArgList(terms))], op)
    elif initel.fHead() is not None:
        fhead = parseFHead(initel.fHead())
        val = parseConstantNumber(initel.NUMBER())
        return FExpression("=", fhead, val)
    else:
        raise Exception("Don't know how to handle initial element " + initel.getText())


def parseProblem(problem):
    name = problem.problemDecl().name().getText()
    domain = problem.problemDomain().name().getText()
    if problem.objectDecl() is not None:
        objects = parseTypeNameList(problem.objectDecl().typedNameList())
    else:
        objects = TypedArgList([])

    init = []
    for initel in problem.init().initEl():
        init.append(parseInitStateElement(initel))

    goal = parseGoalDescription(problem.goal().goalDesc())
    

    return Problem(name, domain, objects, init, goal)


def parseDomainAndProblem(domainfile, problemfile):
    print("Parsing domain", domainfile)
    dinp = FileStream(domainfile)
    dlexer = pddlLexer.pddlLexer(dinp)
    dstream = CommonTokenStream(dlexer)
    dparser = pddlParser.pddlParser(dstream)
    domain = dparser.domain()
    if domain is not None:
        dom = parseDomain(domain)
    else:
        raise Exception("No domain defined in " + domainfile)

    print("Parsing problem", problemfile)
    pinp = FileStream(problemfile)
    plexer = pddlLexer.pddlLexer(pinp)
    pstream = CommonTokenStream(plexer)
    pparser = pddlParser.pddlParser(pstream)
    problem = pparser.problem()
    if problem is not None:
        prob = parseProblem(problem)
    else:
        raise Exception("No problem defined in " + problemfile)


    return (dom, prob)

def main():
    if len(sys.argv) < 2:
        print("Usage: pddl2.py <domain> <problem>")
        return

    domainfile = sys.argv[1]
    problemfile = sys.argv[2]

    (dom,prob) = parseDomainAndProblem(domainfile, problemfile)


    print(dom.asPDDL())
    print(prob.asPDDL())
#    for a in dom.actions:
#        for b in [False, True]:
#            print(a.name, "c", b, list(map(lambda x: x.asPDDL(), a.get_pre(b))))
#        for b in [False, True]:
#            print(a.name, "e", b, list(map(lambda x: x.asPDDL(), a.get_eff(b))))

#    for da in dom.durative_actions:
#        for t in ["start","all","end"]:
#            for b in [False, True]:
#                print(da.name, "c", t, b, list(map(lambda x: x.asPDDL(), da.get_cond(t, b))))
#        for t in ["start","all","end"]:
#            for b in [False, True]:
#                print(da.name, "e", t, b, list(map(lambda x: x.asPDDL(), da.get_eff(t, b))))


if __name__ == "__main__":
    main()