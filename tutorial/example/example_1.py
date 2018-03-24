class MyClass(object):

    def my_method(self):
        pass


def main():
    print __name__

    my_class = MyClass()
    my_class.my_method()

    print '-' * 72
    print 'Ok'


if __name__ == '__main__':
    main()
