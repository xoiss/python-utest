import logging
import sys


logging.basicConfig(level=logging.INFO, stream=sys.stdout)

log = logging.getLogger(__name__)


class Accum(object):

    def __init__(self, person, s=0, n=0):
        self.person = person
        self.s = s
        self.n = n

    def add(self, grade):
        if not 1 <= grade <= 5:
            raise ValueError("grade={} is out of range"
                             .format(grade))
        log.info("add: x={}".format(grade))
        self.s += grade
        self.n += 1
        return self.n


def main():
    print __name__

    print '-' * 72
    print "Actual:"
    print '-' * 72

    accum = Accum('Jhon', 10, 3)
    accum.add(4)
    print("{}'s grade is {}"
          .format(accum.person,
                  float(accum.s) / accum.n if accum.n != 0
                  else 'not defined yet'))

    print '-' * 72
    print "Expected:"
    print '-' * 72

    print "INFO:(__main__|tutorial.example.example_2):add: x=4"
    print "Jhon's grade is 3.5"


if __name__ == '__main__':
    main()
