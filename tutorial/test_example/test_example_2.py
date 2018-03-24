from python_utest import MethodTest, info

from ..example.example_2 import Accum


def main():
    print __name__

    print '-' * 72
    print "Actual:"
    print '-' * 72

    print(MethodTest(Accum.__init__, dict(
        X001=dict(
            raises=TypeError("__init__() takes at least "
                             "2 arguments (1 given)")),
        S001=dict(
            args=("Jhon",),
            final=dict(s=0, n=0)),  # Fails: excessive `person`
        S002=dict(
            args=("Jhon",),
            final=dict(s=0, n=0, person="Jhon")),
        S003=dict(
            args=("Jhon", 10),
            kwargs=dict(n=3),
            returns=None,
            final=dict(person="Jhon", s=11, n=3)),  # Fails: s=10
    )).run().report_cli())

    print(MethodTest(Accum.add, dict(
        S001=dict(
            skip="should be fixed with TASK-12345",
            args=(5,)),  # Otherwise fails: unknown attribute `s`
        S002=dict(
            setup=dict(s=0, n=0),
            args=(5,),
            final=dict(s=5, n=1)),
        I001=dict(
            setup=dict(s=0, n=0),
            kwargs=dict(grade=5),
            returns=1,
            final=dict(s=5, n=1),
            logs=[info("add: x=5")]),
        X001=dict(
            args=(7,),
            raises=ValueError("grade=7 is out of range")),
    )).run().report_cli())

    print '-' * 72
    print "Expected:"
    print '-' * 72

    print "Test Accum.__init__:"
    print ".!.! = 2 failed (of 4)"
    print ": S001 = failed, invalid attributes set [n, person, s], "\
        "expected [n, s], excessive [person], missed []"
    print ": S003 = failed, invalid attribute s=10, expected 11"
    print "Test Accum.add:"
    print "..-. = 1 skipped (of 4)"
    print ": S001 = skipped, should be fixed with TASK-12345"
