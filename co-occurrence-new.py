#!/usr/bin/env python3

import bisect
import numpy
import os
import re
import sys

"""
Describes the type of line, i.e. whether a scene starts, an act starts,
an speaker starts, and so on.
"""
class LineType:
    Description, \
    SceneBegin,  \
    SceneEnd,    \
    ActBegin,    \
    ActEnd,      \
    SpeakerBegin,\
    SpeakerEnd,  \
    Exit,        \
    Text = range(9)

"""
Checks whether a speaker is a "special" speaker. Special speakers
include the stage directions but also songs and "all" characters
speaking.
"""
def isSpecialSpeaker(name):
    return    name == 'STAGE DIR'\
           or name == 'ALL'\
           or name == 'BOTH'\
           or name == 'SONG.'

"""
Classifies a line and returns the line type. 'None' indicates that the
line type is unspecified.

Returns a tuple with the line type and the first extracted token, e.g.
the name of the speaker, the name of the play, and so on. Again, this
token is allowed to be 'None'.
"""
def classifyLine(line):
    reDescription  = r'<\s+Shakespeare\s+--\s+(.+)\s+>'
    reSceneBegin   = r'<SCENE (\d+)>'
    reSceneEnd     = r'</SCENE (\d+)>'
    reActBegin     = r'<ACT (\d+)>'
    reActEnd       = r'</ACT (\d+)>'
    reSpeakerBegin = r'<([A-Z\.\d\s]+)>'
    reSpeakerEnd   = r'</([A-Z\.\d\s]+)>'
    reExit         = r'<Exit(\.?|\s+.*)>'

    if re.match(reDescription, line):
        title = re.match(reDescription, line).group(1).title()
        return LineType.Description, title

    elif re.match(reSceneBegin, line):
        scene = re.match(reSceneBegin, line).group(1)
        return LineType.SceneBegin, scene

    elif re.match(reSceneEnd, line):
        scene = re.match(reSceneEnd, line).group(1)
        return LineType.SceneEnd, scene

    elif re.match(reActBegin, line):
        act = re.match(reActBegin, line).group(1)
        return LineType.ActBegin, act

    elif re.match(reActEnd, line):
        act = re.match(reActEnd, line).group(1)
        return LineType.ActEnd, act

    elif re.match(reSpeakerBegin, line):
        name = re.match(reSpeakerBegin, line).group(1)
        if not isSpecialSpeaker(name):
            # Special handling for singing characters
            if name.endswith("SINGS."):
                name = name[:-6]

            name = name.rstrip()
            return LineType.SpeakerBegin, name

    elif re.match(reSpeakerEnd, line):
        name = re.match(reSpeakerEnd, line).group(1)
        if not isSpecialSpeaker(name):
            return LineType.SpeakerEnd, name

    elif re.match(reExit, line):
        exit = re.match(reExit, line).group(1)

        # Remove a trailing dot if the exit direction refers to
        # a named character
        if exit is not "." and exit.endswith("."):
            exit = exit[:-1]

        exit = exit.strip()
        return LineType.Exit, exit

    elif '<' not in line and line.strip():
        return LineType.Text, line.strip()

    return None, None

""""
Class for describing a complete play with weighted co-occurence matrices.
"""
class Play:
    def __init__(self):
        self.characters = list()
        self.title      = None
        self.A          = None # Weighted adjacency matrix

    """ Adds a new character to the play. """
    def addCharacter(self, name):
        if name not in self.characters:
            bisect.insort( self.characters, name )

    """ List characters in alphabetical order. """
    def getCharacters(self):
        return list( self.characters )

    """ Updates an edge in the adjacency matrix """
    def updateEdge(self, name1, name2, w = 1):
        if self.A is None:
            n      = len(self.characters)
            self.A = numpy.zeros( (n,n), dtype=numpy.float_ )

        u = self.characters.index( name1 )
        v = self.characters.index( name2 )

        self.A[u,v] = self.A[u,v] + w
        self.A[v,u] = self.A[u,v]

    """ Updates multiple edges in the adjacency matrix """
    def updateEdges(self, names, weights):
        for i,first in enumerate(names):
            for j,second in enumerate(names[i+1:]):
                w1 = weights[i]
                w2 = weights[j+i+1]
                self.updateEdge( first, second, w1+w2 )

""" Extremely simple way of counting words in a string """
def countWords(line):
    return len( ''.join(c if c.isalnum() else ' ' for c in line).split() )

#
# HERE BE DRAGONS
#

def isSpecialCharacter(name):
    return    name == stageDirections\
           or name == allCharacters\
           or name == bothCharacters\
           or name == "SONG." # FIXME

reEnteringScene   = r'<SCENE (\d+)>'
reLeavingScene    = r'</SCENE (\d+)>'
reActStart        = r'<ACT (\d+)>'
reActEnd          = r'</ACT (\d+)>'
reSpeakerStart    = r'<([A-Z\.\d\s]+)>'
rePlayDescription = r'<\s+Shakespeare\s+--\s+(.+)\s+>'
reExitUnnamed     = r'<Exit\.?>'

stageDirections = 'STAGE DIR'
allCharacters   = 'ALL'
bothCharacters  = 'BOTH' # FIXME: This should become a regular expression

title      = ""
characters = set()
edges      = set()

play    = Play()

#
# Extract metadata & all characters
#

with open(sys.argv[1]) as f:
    inScene = False
    for line in f:
        t,n = classifyLine(line)

        if t == LineType.Description:
            play.title = n
        elif t == LineType.SceneBegin:
            inScene = True
        elif t == LineType.SceneEnd:
            inScene = False
        elif inScene and t == LineType.SpeakerBegin:
            play.addCharacter(n)

print("Characters: ")

for character in play.getCharacters():
    print("  -", character)

#
# Create co-occurrences
#

with open(sys.argv[1]) as f:
    currentCharacter  = None
    inScene           = False
    activeCharacters  = list()
    wordsPerCharacter = dict()

    for line in f:
        t,n       = classifyLine(line)
        needReset = False # Indicates whether current counter variables
                          # need a reset because the scene changed, for
                          # example.

        if t == LineType.SceneBegin:
            inScene = True
        elif t == LineType.SceneEnd:
            inScene   = False
            needReset = True

            #
            # Create weights: Determine the fraction of words used by
            # all active characters.
            #

            numWords = sum( wordsPerCharacter[c]         for c in activeCharacters )
            weights  = [ wordsPerCharacter[c] / numWords for c in activeCharacters ]

            # Create edges between all characters that are still active
            play.updateEdges( activeCharacters, weights )

        elif t == LineType.SpeakerBegin:
            if n not in activeCharacters:
                activeCharacters.append(n)
                wordsPerCharacter[n] = 0

            currentCharacter = n

        elif t == LineType.Exit and currentCharacter:
            # This is the amount of words in the scene that we have seen
            # so far. We require this to assign a weight for the current
            # character that exits the scene.
            numWords = sum( wordsPerCharacter[c] for c in activeCharacters )

            # The current character left the scene
            if n == ".":
                leavingCharacter = currentCharacter
            # A named character left the scene
            elif n.upper() in activeCharacters:
                leavingCharacter = n.upper()
            else:
                # Check whether the leaving character is a prefix
                # of any named character
                candidates = [ c for c in activeCharacters if c.startswith( n.upper() ) ]
                if len(candidates) == 1:
                    leavingCharacter = candidates[0]
                else:
                    print("Warning: Unable to detect leaving character: '%s'" % n.upper())
                    leavingCharacter = None

            if leavingCharacter:
                for c in activeCharacters:
                    if c is not leavingCharacter:
                        w1 = wordsPerCharacter[leavingCharacter] / numWords
                        w2 = wordsPerCharacter[c]                / numWords
                        play.updateEdge( leavingCharacter, c, w1+w2 )

                if leavingCharacter == currentCharacter:
                    currentCharacter = None

                activeCharacters.remove( leavingCharacter )

        elif t == LineType.Text:
            if not currentCharacter:
                print("Warning: I cannot assign this text to someone...")
            else:
                wordsPerCharacter[currentCharacter] += countWords(n)

        if needReset:
            currentCharacter  = None
            inScene           = False
            activeCharacters  = list()
            wordsPerCharacter = dict()

#
# HERE BE DRAGONS
#

with open(sys.argv[1]) as f:
    inScene = False
    for line in f:

        if re.match(rePlayDescription, line):
            title = re.match(rePlayDescription, line).group(1).title()
        elif re.match(reEnteringScene, line):
            inScene           = True
        elif re.match(reLeavingScene, line):
            inScene = False
        elif inScene and re.match(reSpeakerStart, line) and not re.match(reActStart, line):
            character = re.match(reSpeakerStart, line).group(1)
            if not isSpecialCharacter(character):
                characters.add( character )

print("Characters: ")

for character in characters:
    print("  -", character)

characterIndices = dict()

for index, character in enumerate(sorted(characters)):
    characterIndices[character] = index

n      = len(characters)
A      = numpy.zeros( (n,n), dtype=numpy.float_ )

#
# Extract co-occurences
#

with open(sys.argv[1]) as f:
    charactersInScene = set()
    wordsPerCharacter = dict()
    currentCharacter  = None
    numWordsInScene   = 0

    for line in f:
        if re.match(reEnteringScene, line):
            inScene           = True
            charactersInScene = set()
            wordsPerCharacter = dict()
            currentCharacter  = None
            numWordsInScene   = 0
        elif re.match(reLeavingScene, line):
            inScene = False
            print("Characters in the current scene:", file=sys.stderr)
            for character in sorted(charactersInScene):
                print("  - %s" % character, file=sys.stderr)

            x = sorted( [ (characterIndices[c], wordsPerCharacter[c]) for c in charactersInScene ], key=lambda t: t[0] )
            for i in range(len(x)):
                for j in range(i+1,len(x)):
                    u      = x[i][0]
                    v      = x[j][0]
                    w      = ( x[i][1] + x[j][1] ) / numWordsInScene
                    A[u,v] = A[u,v] + w # Increase weight
                    A[v,u] = A[u,v]

        elif inScene and re.match(reSpeakerStart, line) and not re.match(reActStart, line):
            character = re.match(reSpeakerStart, line).group(1)
            # FIXME: Still require special handling for "all" characters within
            # a scene.
            if not isSpecialCharacter(character):
                currentCharacter = character
                charactersInScene.add( character )

        elif inScene and re.match(reExitUnnamed, line):
            indices = sorted( [ characterIndices[c] for c in charactersInScene ] )
            u       = characterIndices[currentCharacter]
            w       = wordsPerCharacter[currentCharacter] / numWordsInScene
            for i in range(len(indices)):
                v      = indices[i]
                A[u,v] = A[u,v] + w # Increase weight
                A[v,u] = A[u,v]

            print(currentCharacter, "left the scene.")
            charactersInScene.remove(currentCharacter)

        elif '<' not in line and line.strip():
            numWords        = len( ''.join(c if c.isalnum() else ' ' for c in line).split() )
            numWordsInScene = numWordsInScene + numWords
            if currentCharacter:
                wordsPerCharacter[ currentCharacter ] = wordsPerCharacter.get( currentCharacter, 0 ) + numWords

#
# Output
#

outputName = title.replace(" ", "_") + ".net"

with open(outputName, "w") as f:
    print("%%%s" % title, file=f)
    print("*Vertices %d" % len(characters), file=f)
    for index, name in enumerate( sorted(characters) ):
        print( "%d \"%s\"" % ( index+1,name.title() ), file=f )

# Make this an undirected graph
    print("*Edges", file=f)

    nRows, nColumns = A.shape
    characterNames  = sorted(list(characters))

    for row in range(nRows):
        for column in range(row+1,nColumns):
            if A[row,column] > 0:
                print( "%03d %03d %f" % (row+1, column+1, A[row,column]), file=f )
