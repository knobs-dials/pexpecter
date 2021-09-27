(currently rewriting for more general use, hang on)

# pexpecter

Wraps a rule system around python's pexpect module,
which is mostly an ordered list of `("if you see this", "then say/do this")` pairs.

This is shorter to write, yet not much more functional, than what you'd do handing a list to expect() (...which you typically want to do when you want to deal with extra/missing that are conditional on config/environment/varying versions, reordered questions, and such).

If you need something more complex than this, chances are you want to skip this and build a state machine instead.


## Examples

It's actually somewhat hard to think of good examples.

Many examples you see out there are remote execution, but many cases are simple enough that a sequence of expect()s is often just as simple, and pxssh might be an easier base to start with.


### rclone example

```python
import pexpect
import helpers_pexpect

rules = [
    ["(No remotes|Current remotes:)",'n'],
    ["name>",                        'myname'],
    ["Storage>",                     'sftp'],
    ["host>",                        'example.com'],
    ["port>",                        '22'],
    ["user>",                        'myuser'],
    ['SSH password, leave',          'y'],
    ['password:',                    'hackme'], # will also match the confirm. Would be more readable to separate that out
    ['key_file>',                    ''],
    ['Only PEM encrypted key[^>]+>', 'n'],
    ['key_use_agent>',               ''],
    ['use_insecure_cipher>',         'true'],
    ['disable_hashcheck>',           ''],
    ['Edit advanced config[^>]+>',   'n'],
    ['Yes this is OK',               ('y', ('sleep',0.5), None) ]  
]

proc = pexpect.spawn('rclone config')
helpers_pexpect.interact_rules( proc, rules )
# if we can assume there is a rule that means that function only returns once we're done, we can now just:
proc.close()
```

The above "make an rclone config" example works, but is **actually a good example of when you probably do _NOT_ want this module**:

For a good part because rclone offers a parameter-based way to do it, which is more controlled, the parameters are probably more stable, and is easier to test for failure.

But also, these rules are basically the questions one by one in order, so doesn't do anything more than a series of expect()s and sendline()s.

In fact, this is potentially more fragile. Consider the first and last rules:
- The first rule because the wording of the first summary you get, and its prompt, both depend on whether there were remotes already defined or not. That requires some trial and error to figure out.
- The last rule could probably be "y/e/d>", but I'd have to know it always says that (more trial and error) _and_ that nothing else does. The string used here is _probably_ more unique.
...both these issues might be easier to resolve with a series of expect()s and sendline()s, because you know where in the sequence you are. And sometimes you can build something more like a state engine.


That last sleep is there to make sure we don't kill the process  before it's written the config. This may not be necessary.
It also feels pretty fragile - the better fix would be to detect the next prompt before exiting, which is currently not easy because there's no state.

(also, you may want a delay on password entry due to terminal noecho sometimes taking a little time, but that's true for any automation)


### ctffind example

```python
   rules = [
        ['Input image file name[^:]*:',                 inputmrc ],

        ['Output diagnostic filename[^:]*:',            diagbase  ],
        ['Output diagnostic image file name[^:]*:',     diagbase  ], # v4.1

        ['Pixel size[\s0-9.,\x1b\[\]m]+:',              '%f'%pixelsize_A],  # should avoid matching the "Pixel size for fitting" in the pre-calculation or post-calculation summary
        ['Acceleration voltage[^:]*:',                  '%.1f'%acc_kV],
        ['Spherical aberration[^:]*:',                  '%f'%sphericalaberration],
        ['Amplitude contrast[^:]*:',                    '%f'%amplitudecontrast_frac],

        ['Size of power spectrum to compute[^:]*:',     '%d'%spectrumsize_pixels], # CONSIDER: ensure twopower?
        ['Size of amplitude spectrum to compute[^:]*:', '%d'%spectrumsize_pixels], # v4.1

        ['Minimum resolution[^:]*:',                    '%f'%minres_A],
        ['Maximum resolution[^:]*:',                    '%f'%maxres_A],
        ['Minimum defocus[^:]*:',                       '%f'%mindef_A],
        ['Maximum defocus[^:]*:',                       '%f'%maxdef_A],
        ['Defocus search step[^:]*:',                   '%d'%defstep_A],

        ['Do you know what astigmatism is present[^:]*:', 'no'],  # v4.1
        ['Do you expect very large astigmatism[^:]*:',    'yes'], # v4.1. apparently >1000A is considered very large.
        ['Use a restraint on astigmatism?[^:]*:',         'yes'], # v4.1. Penalise above given value

        ['Expected \(tolerated\) astigmatism[^:]*:',    '%f'%astigpenaltyover_A], # v4.1

        ['Do you want to set expert options[^:]*:',     'no'], # v4.1. HAven't checked which they are yet

        ['Find additional phase shift[^:]*:',           phaseshift_yesno],
        # only get asked if you answer yes to phase shift:
        ['Minimum phase shift[^:]*:',                   '%.2f'%phaseshift_minrad],
        ['Maximum phase shift[^:]*:',                   '%.2f'%phaseshift_maxrad],
        ['Phase shift search step[^:]*:',               '%f'%phaseshift_steprad],

        ['more exhaustive search',                      'no'],

        ['Summary information',                         None], # it's starting -- give back control
    ]
```

The ctffind example makes more sense as an example, in that 
- questions are worded quite uniquely
- some questions only conditionally appear (phase shift search details, when you look for phase shift at all), meaning this unifies distinct uses
- the wording in ctffind versions changed a little, meaning this more easily supports multiple versions
- it demonstrates a "hand back control early" rule, plus how you might then wait for it (see full example).
  - Which this particular code doesn't need, but in general you might find uses for such non-blocking behaviour.
  - note that it would be simpler to comment out the last rule -- the function will then stay in control until it sees EOF.
- (and yes, ctffind does have a parameter style, but some experimental/beta features were only in the question style)

I used this example in real software.  It's not easy to test, as you'ld have to download ![ctffind](https://grigoriefflab.umassmed.edu/ctf_estimation_ctffind_ctftilt) and some example data (say, take one .mrc file from ![EMPIAR-10519](https://empiar.pdbj.org/entry/10519/)) to actually see it work. And do some reading up to understand what this electron microscopy tool is even calculating. I'm guessing you don't particularly care.


## Rule format

The rule_list argument on interact_rules is a set of tuples. 
- The first part is a regex to match
- If the second is
    - a string, it is sent as-is

    - None,   please hand over control back to me" with retval -1
        meant for "that was the question part done, now we wait for the process to do what it does"
        If you don't, this function stays in control until it sees EOF.

    - False,  please hand over control back to me with retval -2
        meant for "that was an error message, let the overall return reflect that"

    - a list/tuple: do multiple things. Each item can be 
      - any of the above (probably most commonly a string), or
      - ('print', what )
      - ('sleep', howlong_sec)
      - ('del',   rulebymatch)          (often itself - see below)



## Limitations

- You would generally prefer CLI parameters as they are less likely to change than question-answer interfaces.
  I would recommend only using this if you have no other choice, 
  and ideally you want to also control the versions of the command you're running rules on.

- the more questions there are, the more likely it is that a rule matches something you didn't think about.
  Make rules as specific as possible, and think about how you would break this intentionally.
  - the 'remove rule' thing was aimed at this, see below

- Various cases that provide only a question-answer interface do so intentionally,
  to make you think about what you're doing.  Keep thinking.


## TODO / CONSIDER: 
- wrap some common boilerplate-ish code, e.g.
  - our own spawn wrapper, so that we can e.g. allow matching on stderr output.  This seems to have a good idea: https://stackoverflow.com/questions/27179383/extracting-stderr-from-pexpect

- special-cased exit for "nothing matches"?

- test the "remove rule" thing.
  I've rarely used this construction, so I'm not 100% on whether it still works as expected.
  The idea was that if everything should be answered once, rules can remove themselves to avoid accidentally matching something later.

- read up on more peculiarities, like 
  https://pexpect.readthedocs.io/en/stable/commonissues.html
  https://helpful.knobs-dials.com/index.php/Pexpect#pexpect
