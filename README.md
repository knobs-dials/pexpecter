# pexpecter

Wraps python's standard pexpect module with a rule system.

Which mostly works out as a simpler-to-user variant of expect_list(),
in that it lets you deal with extra/missing questions depending on config 
or varying versions (e.g. MPI, PBS) reordered questions, and such.

(currently rewriting for more general use, hang on)


This was written for a few different pieces of software that either only work in a question-answer style,
and choose to expose beta features in question mode but not in parameters.

The rule system is mostly an ordered list of
  ("if you see this", "then say/do this") 
pairs, including special cases that means 'hand back control now'.


If you need something more complex than this, chances are you should be building a state machine instead.


