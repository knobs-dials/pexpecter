(currently rewriting for more general use, hang on)


# pexpecter

Wraps a rule system around python's pexpect module,
which is mostly an ordered list of `("if you see this", "then say/do this")` pairs.


It lets tou deal with things like extra/missing that are conditional on config 
or varying versions (e.g. MPI, PBS) reordered questions, and such.

And yes, is mostly just a slightly simpler to use variant of handing a list to expect(),
and aims to wrap some common boilerplate-ish code too.


This was written for a few different pieces of software that either only work in a question-answer style,
and choose to expose beta features in question mode but not in parameters.

If you need something more complex than this, chances are you should be building a state machine instead.


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
    ['password:',                    'hackme'], # will also match the confirm. Would be more readable to 
    ['key_file>',                    ''],
    ['Only PEM encrypted key[^>]+>', 'n'],
    ['key_use_agent>',               ''],
    ['use_insecure_cipher>',         'true'],
    ['disable_hashcheck>',           ''],
    ['Edit advanced config[^>]+>',   'n'],
    ['Yes this is OK',               ('y', ('sleep',0.2), None) ]  # sleep is probably not necessary, but can't hurt.
]

proc = pexpect.spawn('rclone config')
helpers_pexpect.interact_rules( proc, rules )
# if we can assume there is a rule that means that function only returns once we're done, we can now just:
proc.close()
```

The above "make an rclone config" example works, but is actually an example of when you probably do _NOT_ want this module.

For starters, rclone offsers a parameter-based way to do it, which is more controlled and less fragile.

Also, that list of rules is just the questions one by one in order, so doesn't do anything more than a series of expect()s and sendline()s.
And if the questions do change a little, then the list-and-index variant of pexpect would still do, and this module adds little.

The first and last rules demonstrates how you sometimes need to write rules based on trial and error:
- The first because the wording in the first summary you get, and its prompt, depends on whether there were remotes already defined or not.
- The last could probably be "y/e/d>", but I'd have to know it always says that, and nothing else does. The string used here is probably more unique.


### ctffind example

Rules are
```python
   rules=[
        ['Input image file name[^:]*:',                 inputmrc ],

        ['Output diagnostic filename[^:]*:',            diagbase  ],
        ['Output diagnostic image file name[^:]*:',     diagbase  ], # v4.1

        ['Pixel size[\s0-9.,\x1b\[\]m]+:',            '%f'%pixelsize_A],  # written that way to not match the "Pixel size for fitting" in the pre-calculation or post-calculation summary
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

        ['Expected \(tolerated\) astigmatism[^:]*:',   '%f'%astigpenaltyover_A], # v4.1

        ['Do you want to set expert options[^:]*:',   'no'], # v4.1. HAven't checked which they are yet

        ['Find additional phase shift[^:]*:',        phaseshift_yesno],
        # only get asked if you answer yes to phase shift:
        ['Minimum phase shift[^:]*:',                '%.2f'%phaseshift_minrad],
        ['Maximum phase shift[^:]*:',                '%.2f'%phaseshift_maxrad],
        ['Phase shift search step[^:]*:',            '%f'%phaseshift_steprad],

        ['more exhaustive search',                   'no'],

        ['Summary information',                     None], # it's starting -- give back control
    ]
```

The ctffind example makes more sense as an example, in that 
- some questions only conditionally appear (phase shift search details, when you look for phase shift at all)
- the wording in some questions changed, so this supports multiple versions.
- there is a parameter style, but some experimental/beta features were only in the question style
- it demonstrates a "hand back control early" rule, plus how you might wait for it instead.
  - Which this particular code doesn't really use that, but in general you might find uses for such non-blocking behaviour.
  - it would be simpler to comment out the last rule -- the function will then stay in control until it sees EOF.

I used this example in real software, and it works, but you'ld have to download ![ctffind](https://grigoriefflab.umassmed.edu/ctf_estimation_ctffind_ctftilt) and some example data (say, take one .mrc file from ![EMPIAR-10519](https://empiar.pdbj.org/entry/10519/)) to actually see it work.
And do some reading up to understand what this electron microscopy tool is even calculating. I'm guessing you don't particularly care.


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

- Question-answer interfaces are more likely to change than CLI parameters do.  Which is why you'ld typically prefer those.
  I would recommend only using this if you need it, 
  and ideally also control the versions of the command you're running this on.

- the more questions there are, the more likely it is that a rule matches something you didn't think about.
  Make rules as specific as possible, and think about how you would break this intentionally.
  - the 'remove rule' thing was aimed at this, see below

- Various cases that provide only a question-answer interface do so intentionally,
  to make you think about what you're doing.  Keep thinking.


## TODO:

- test the "remove rule" thing.
  I've rarely used this construction, so I'm not 100% on whether it still works as expected.
  The idea was that if everything should be answered once, rules can remove themselves to avoid accidentally matching something later.

- special-cased exit for "nothing matches"?

- allow matching on stderr output. This seems to have a good idea: https://stackoverflow.com/questions/27179383/extracting-stderr-from-pexpect

- read up on more peculiarities, like 
  https://helpful.knobs-dials.com/index.php/Pexpect#pexpect
  https://pexpect.readthedocs.io/en/stable/commonissues.html
