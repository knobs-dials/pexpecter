#!/usr/bin/python
''' Wraps pexpect with a rule system that makes my life simpler
    Written by Bart Alewijnse
'''
import sys
import time
import pexpect

import helpers_shellcolor as sc

def interact_command(pexpect_object, command, waitfor=None):
    """ Sends a command.

        Optionally waits for a text pattern before doing so (waitfor argument),
          e.g. useful when you are talking to a shell-style CLI with a prompt we can match
          as a guard against sending things too early.
    """
    if waitfor:
        pexpect_object.expect( waitfor )
    pexpect_object.sendline(command)
    

def interact_rules(pexpect_object, rule_list, timeout=None, debug=0 ):
    ''' Interacts with a underlying program, with a given set of rules.

        Returns  the min( the return codes it saw from individual rules ) , which will be
                 0 if we saw EOF  -- we assume that was expected  
                -1 if a rule handed back control early  (rule used None)
                -2 when we notice mention of an error   (rule used False
                -3 when we see a timeout                (if timeout!=None)



        If timeout=None (default), all waiting is indefinite. 
        This is a conservative default you probably want to change, but keep in mind
        - that often the likeliest reason for a timeout is an error that is not matched by any rule
        - that setting this to a "this process usually takes this long" will fail unreasonably e.g. on high server load. 
          I'd suggest either
           - a much longer than typical  timeout to not fail when the 
           - dealing with the -3 response explicitly with retrying  (often more work, but more correct)

        Keep in mind that this doesn't close the connection with the child, so ideally you do this yourself.

        If you are interacting with a custom shell, you may wish to detect the prompt. The original version of this had one hardcoded,

        It would be nice if we can distinguish between timeout matching a question (seconds at most) and a long-running command (days)
        (would it do to have a huge default, and a lowish timeout on expects from this function?)


        debug=0  print nothing   (beyond what print rules instruct)
        debug=1  prints the exchange 
        debug=2  will print what we match and how we are handling rules, and is meant for debugging your rules
        debug=3  is a more verbose,  and prints the interaction, and is meant for debugging this module

    '''
    # TODO: create our own spawn (to be more flexible), move this there
    if debug>0:
        pexpect_object.logfile = sys.stdout
    pexpect_object.setecho( False ) # tty echo 


    ### Make sure we deal with EOF and with timeouts ourselves  (see pexpect behaviour - it handles these differently if they're in the list)
    if pexpect.EOF not in list(e[0] for e in rule_list):
        rule_list.append( (pexpect.EOF,'') )
    if pexpect.TIMEOUT not in list(e[0] for e in rule_list):
        rule_list.append( (pexpect.TIMEOUT,'') )

    # zealous checking
    EOF_index, TIMEOUT_index, ERROR_index  =  None, None, None
    i = 0
    for match,say in rule_list:
        if match==pexpect.EOF:
            EOF_index=i
        if match==pexpect.TIMEOUT:
            TIMEOUT_index=i
        #if match==_pexpect_error:
        #    ERROR_index=i
        i+=1
    assert EOF_index != None
    assert TIMEOUT_index != None
    #assert ERROR_index != None

    # rule processing - should exit for one of a bunch of reasons
    while True:
        list_patterns = list(e[0]  for e in rule_list)  # only necessary after a del, but it's a cheap enough operation
        
        mi = pexpect_object.expect( list_patterns, timeout=timeout )  
        if debug >= 2:
            if debug >= 3:
                if pexpect_object.match==pexpect.EOF:
                        matchstr = 'EOF'
                else:
                    matchstr = pexpect_object.match.group()
                print( "\nMATCH: '%s' / '%s' / '%s'"%(
                    sc.darkgray( str(pexpect_object.before) ), 
                    sc.gray(     matchstr ),
                    sc.darkgray( str(pexpect_object.after) ),
                ) )

            if not hasattr( pexpect_object.match, 'group' ): # EOF and TIMETOUT are not regexp matches...
                print( sc.brightyellow( ("\n  Matched response %r"%( pexpect_object.match ))) )
            else:
                print( sc.brightyellow( ("\n  Matched response text %r"%( pexpect_object.match.group() ))) )
            print( sc.orange( "  with rule value %s"%( repr(rule_list[mi]) ) ) )
            
        if mi == EOF_index:
            if debug >= 2:
                print( "EOF" )
            return 0 # assume we're fine
        elif mi == TIMEOUT_index:
            print( "Timed out" )
            if debug >= 2:
                print( "TIMEOUT" )
            return -3
        else:

            def respond(response):
                if debug >= 3:
                    print( sc.cyan("    Dealing with rule item %r"%(response,)) )

                if type(response) in (tuple,list): # reactions distinguished from string responses, including those with argumets

                    if response[0]=='del': 
                        # This is an unfinished idea
                        # deletes the *first* rule with the matching pattern (exact string match)
                        # CONSIDER: a way of deleting the rules this came from (requires index, not just the response, though)
                        delete_i=None
                        for ri in range(len(rule_list)):
                            if rule_list[ri][0]==response[1]:
                                delete_i=ri
                                break
                        if delete_i!=None:
                            if debug >= 3:
                                print( sc.brightcyan("    removing rule, index %s: %r"%(delete_i,rule_list[delete_i])) )
                            rule_list.pop(delete_i)
                            list_patterns = list(e[0]  for e in rule_list)                            
                        return 0, rule_list
                        
                    elif response[0] == 'sleep':  # ideally this is never necessary. CONSIDER: removing
                        sleeplen = float(response[1])
                        time.sleep(sleeplen)
                        return 0, rule_list

                    elif response[0] == 'print': # 
                        print( response[1] )
                        return 0, rule_list

                    else:
                        print( sc.red('  Do not know action %r, skipping...'%response[0]) )
                        return 0, rule_list                    

                elif response==None: #that's our "terminate rule processing now, we're okay" message.
                    if debug >=2:
                        print( sc.yellow("  Rule used None, signaling that we're done") )
                    #TODO: actually handle this case.
                    return -1, rule_list
                
                elif response==False: # our "terminate now, that was an error" message.
                    print( "Underlying command reported a problem: %s"%sc.red( repr(pexpect_object.match.group()) ) )
                    return -2, rule_list

                else: # assumes it's the typical case, a string to send
                    pexpect_object.sendline(response)
                    return 0, rule_list
                                        
            response_val = rule_list[mi][1]
            minresp = 999
            if type(response_val) in (list, tuple): # multiple things to do
                for r in response_val:                    
                    retval, rule_list = respond( r ) 
                    minresp = min( minresp, retval )
                    #if debug >= 2:
                    print( '    respond() exited with ',minresp )
                if minresp <= -1: # break after the rule processing is done
                    retval = minresp
                    break
                #print "  overall response:",minresp
                if minresp <= -2 :
                    #if debug >= 1:
                    print( "Stopping1...  (%d)"%minresp )
                    retval = minresp
                    break
                    #return minresp
                    
            else: # single thing to do
                retval, rule_list = respond(response_val)
                if retval <= -2:
                    #if debug>0:
                    print( "Stopping2...  (%d)"%retval )
                    return retval
    
    return minresp
