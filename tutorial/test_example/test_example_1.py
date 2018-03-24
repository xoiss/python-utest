from python_utest import MethodTest

from ..example.example_1 import MyClass


def main():
    print __name__

    print '-' * 72
    print "Actual:"
    print '-' * 72

    print(MethodTest(MyClass.my_method, dict(
        S={},  # Just runs my_method() in a sandbox
    )).run().report_cli())

    print '-' * 72
    print "Expected:"
    print '-' * 72

    print "Test MyClass.my_method:"
    print ". = 1 succeeded"
