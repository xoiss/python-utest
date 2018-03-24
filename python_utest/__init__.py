from copy import deepcopy
from sys import modules


class MethodTest(object):
    """
    Provide simple framework for testing class methods.

    This micro framework delivers a simple descriptive language for
    tests and a tiny number of workflows typical for the majority of
    use-cases when a simple class method should be tested.

    It allows describing in short form what is given in the beginning,
    what should be done, what should happen, and what is expected in the
    end. The core idea is to make the test suite description as compact
    as possible and focus on the Test and the coverage but not the other
    syntactic stuff like innumerous assertions or parametrized fixtures.

    This micro framework may be used both as a standalone facility for
    simple cases and as a helper with conventional testing frameworks.

    Instantiate this class passing a method-to-be-tested and the test
    suite to the initializer. Then call `run` once to execute the test
    suite. After `run` finishes the raw test results are accessible in
    `statement` and the formal test suite name is in `caption`. Call
    `report_...` to obtain different formatted or aggregated reports or
    slices with test results.

    Example of usage, the simplest case:

        class MyClass(object):

            def my_method(self):
                pass

        print(MethodTest(MyClass.my_method, dict(
            S={},  # Just runs my_method() in a sandbox
        )).run().report_cli())

    Slightly more complex example:

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

    More complicated examples are given below in the module.

    The whole test suite is run for the same single method of a class.
    If you wish to test other methods of the target class, you have to
    establish more instances of `MethodTest` for them.

    With respect to the test suite, the framework is able to:
    - create an artificial target class instance (sandbox) to run the
            tested method with
    - install given mock methods in the sandbox overloading the native
            methods if such are used by the tested method
    - setup the initial state of the sandbox
    - verify the final (outgoing) state of the sandbox after the tested
            method completed
    - pass positional and named arguments to the tested method
    - verify the result returned by the method
    - catch and verify exceptions raised by the tested method
    - create a mock object to substitute the global log if such is used
            by the tested method
    - collect and verify messages logged to the global log
    - disable automatic calls to `__init__` and `__del__` methods of the
            target class during tests
    - perform tests for (almost) all methods of the target class
            including `__init__` and `__del__` methods
    - make detailed diagnostic messages in the case of test failure
    - skip particular tests in the suite or the whole suite
    - run single test of the suite (useful for debug of the failed test)

    Feel free to establish wrapper classes to implement more complex
    mocks overloading the tested class methods.

    See further docstrings for more details.
    """

    LEVELS = 'XEWIS'  # Test and log levels: eXcept, Error, Warn, Info, Success

    SUCCEEDED = 0  # Test has finished successfully, all checks were met
    SKIPPED = 1  # Test was skipped, i.e. it was not run
    FAILED = 2  # Test was run, but it has failed some checks
    CRASHED = 3  # Test was not run due to invalid description

    MARKS = {
        SUCCEEDED: dict(pict='.', verb='succeeded'),
        SKIPPED: dict(pict='-', verb='skipped'),
        FAILED: dict(pict='!', verb='failed'),
        CRASHED: dict(pict='#', verb='crashed'),
    }

    @staticmethod
    def _level_raises(level):
        return MethodTest.LEVELS[level] in 'XE'

    @staticmethod
    def _level_logs(level):
        return MethodTest.LEVELS[level] in 'EWI'

    def __init__(self, method, suite=None):
        """
        Perform basic checks and preparatory processing of the test
        suite.

        Assign arguments with the following:
        - `method` -- an unbound method of a class to be tested
        - `suite` -- dictionary containing individual test descriptors

        This framework is able to run tests only for unbound methods.
        The so-called class-methods and static-methods, and simple
        functions are not allowed and cannot be tested by this
        framework. Methods bound to class instances are also not
        allowed. The `method` parameter must be assigned with something
        like `MyClass.my_method` where `my_method` has at least one
        parameter and the first parameter is `self`.

        The `suite` parameter must be assigned with a dict object
        holding all test descriptions. In the ultimate case, the test
        suite may be an empty dict, i.e. containing no tests. Item keys
        must be strings starting with uppercase letter denoting test and
        log level, one of X, E, W, I, S. The item key is considered as
        the test name within the suite. Item values must be dict objects
        describing particular test cases.

        See docstrings to `run` method and `MethodTestAdapter` class for
        more details on test description.

        The test suite given as a dict object is converted to list by
        this initializer with strict order of tests. First, all tests
        are grouped according to their test and log level -- i.e.,
        according to the first letter in the test item key: invalid test
        identifier, unknown group label, eXcept, Error, Warn, Info,
        Success. Then groups are ordered with decreasing level as shown
        above, so that all X-tests are run the first and all S-tests are
        run the last. Note that if there are invalid identifiers or
        unknown group labels, such tests run prior to X-tests (indeed
        they all will crash). And finally tests of the same level are
        ordered alphabetically with their identifiers within the group.
        This order is held throughout the whole framework.
        """

        if not hasattr(method, 'im_self') or method.im_self:
            raise TypeError("method={!r}, functions, static, class "
                            "and bound methods are not allowed, "
                            "unbound method is required".format(method))

        if suite is None:
            suite = {}

        if not isinstance(suite, dict):
            raise TypeError("suite is instance of '{}', must be 'dict'"
                            .format(type(suite).__name__))

        self.suite = map(lambda (tid, test): (MethodTest._tid_level(tid),
                                              tid, test),
                         suite.viewitems())

        self.suite.sort(key=lambda (level, tid, test): (level, tid))

        self.method = method

    @staticmethod
    def _tid_level(tid):
        return (MethodTest.LEVELS.find(tid[0])
                if isinstance(tid, str) and tid else None)

    def run(self, statement=None, variant=None, skip=None, single=None):
        """
        Run the test suite until the end and save results.

        Assign arguments with the following:
        - `statement` -- assign with externally kept statement to 
                aggregate results of different suites and their runs
                into a single (or dedicated) statement
        - `variant` -- assign with a string or other representative
                object briefly describing the dynamic configuration
                (variant) of the test suit run this time when running in
                cycle
        - `skip` -- set to anything which evaluates to boolean `True` if
                the whole test suite shall be skipped. If it is assigned
                with a string object, such string will be saved as the
                diagnostic message in the statement for all tests
        - `single` -- set to one of test names in the suite to run only
                that particular test. This is useful for debug purposes
                when such test fails. All the other tests will be
                omitted (not marked as skipped, but omitted completely).
                This parameter must not be enabled simultaneously with
                `skip` or when the target test contains `skip` item in
                its individual description which evaluates to `True`.
                The target test must exist in the suite and the name 
                must be valid. The test names are case sensitive.

        This method runs through the list of all tests in the suite,
        validates tests descriptions, runs individual tests with the
        test-harness, collects test results and saves them sequentially
        into the `statement` in uniform manner. If a test name or the
        test description is formally invalid, the test is marked CRASHED
        and a diagnostic message with the observed invalidity is saved.
        If a test was run in the test-harness but it reports that the
        test failed, the test is marked FAILED and the detailed
        diagnostic message provided by the test-harness is saved. If a
        test is skipped, it is marked SKIPPED and if `skip` is a string,
        such string is saved as the diagnostic message. If a test was
        run and the test-harness reports success, the test is marked
        SUCCEEDED, no diagnostic is written here. The order in which
        tests are run is formalized with the rule given in the docstring
        to `__init__` method. If `single` evaluates to `True` all other
        tests are omitted, no results are saved for them in statement.

        Generally this method may be called multiple times on the same
        test instance as soon as it's idempotent by design. It allows
        running dynamically parametrized suite in cycle. Results are
        saved serially into the `statement`, so it's better to use
        `variant` to distinguish results after different runs. Also
        `statement` may be purged or replaced manually between runs when
        desired. Note that when `report_...` is called after particular
        run it will treat only the last bound `statement`.

        This method returns its `self` to allow chained calls. It may be
        helpful to call `report_...` immediately after a single `run`.
        """

        self.statement = statement if statement else []

        if variant:
            # TODO: Need to rework the statement processing
            raise NotImplementedError("Don't use `variant` parameter!")

        if skip and single:
            raise ValueError("`skip` and `single` must not be "
                             "enabled simultaneously")

        if single:
            if MethodTest._tid_level(single) < 0:
                raise ValueError("invalid test identifier single={!r}, "
                                 "must be 'str' starting with one of '{}'"
                                 .format(single, MethodTest.LEVELS))

            tests = filter(lambda (level, tid, test): tid == single,
                           self.suite)
            if not tests:
                raise ValueError("test identifier single={!r}, not found"
                                 .format(single))

            assert len(tests) == 1
            _, _, test = tests[0]

            if 'skip' in test and test['skip']:
                raise ValueError("test identifier single={!r}, test is "
                                 "skipped individually".format(single))

        for (level, tid, test) in self.suite:
            if single and single != tid:
                continue  # Don't append results for omitted tests

            if skip:
                self.statement.append(dict(
                    tid=tid, mark=MethodTest.SKIPPED,
                    msg=skip if isinstance(skip, str) else None))
                continue

            if level < 0:
                self.statement.append(dict(
                    tid=tid, mark=MethodTest.CRASHED,
                    msg="invalid test identifier {!r}, must be 'str' starting "
                        "with one of '{}'".format(tid, MethodTest.LEVELS)))
                continue

            if not isinstance(test, dict):
                shorten = lambda s, n: ("{}...{}".format(s[:n], s[-1])
                                        if len(s) > n else s)
                self.statement.append(dict(
                    tid=tid, mark=MethodTest.CRASHED,
                    msg="invalid test descriptor {}, must be 'dict'"
                        .format(shorten(repr(test), 100))))
                continue

            if 'skip' in test and test['skip']:
                self.statement.append(dict(
                    tid=tid, mark=MethodTest.SKIPPED,
                    msg=(test['skip'] if isinstance(test['skip'], str)
                         else None)))
                continue

            if MethodTest._level_raises(level) != ('raises' in test):
                self.statement.append(dict(
                    tid=tid, mark=MethodTest.CRASHED,
                    msg="'raises' is {} in test descriptor".format(
                        'specified' if 'raises' in test else 'omitted')))
                continue

            if {'raises', 'returns'} <= set(test.viewkeys()):
                self.statement.append(dict(
                    tid=tid, mark=MethodTest.CRASHED,
                    msg="'returns' is specified in test descriptor"))
                continue

            if MethodTest._level_logs(level) and 'logs' not in test:
                self.statement.append(dict(
                    tid=tid, mark=MethodTest.CRASHED,
                    msg="'logs' is omitted in test descriptor"))
                continue

            failed = self.harness(test)

            if failed:
                self.statement.append(dict(
                    tid=tid, mark=MethodTest.FAILED,
                    msg=failed if isinstance(failed, str) else None))
            else:
                self.statement.append(dict(
                    tid=tid, mark=MethodTest.SUCCEEDED, msg=None))

        return self

    # TODO: Move all reports into the Statement class

    def report_statement(self, severity=None):
        """
        Return list of dicts with tests execution results. Each item
        corresponds to one test in the suite. Tests are listed in the
        order commonly accepted in this framework, see docstring to
        `__init__` method.

        Items for marks having severity level lower than specified with
        `severity` are omitted. Left `severity=None` to include all
        levels into the report.

        Each item in the returned list includes fields:
        - `tid` -- unique test identifier taken from the suite
        - `mark` -- numeric code of the mark, CRASHED=3, FAILED=2,
                SKIPPED=1, SUCCEEDED=0
        - `msg` -- string containing detailed diagnostic message or None
        """

        return filter(lambda rec: rec['mark'] >= severity, self.statement)

    def report_bar(self):
        """
        Return string of characters (ASCII pictograms) representing
        completion marks of all tests in the statement. Tests are listed
        in the order commonly accepted in this framework, see docstring
        to `__init__` method.

        The following characters are used for different marks:
        - '#' -- for tests which CRASHED
        - '!' -- ... FAILED
        - '-' -- ... SKIPPED
        - '.' -- ... SUCCEEDED
        """

        return ''.join(map(lambda rec: MethodTest.MARKS[rec['mark']]['pict'],
                           self.statement))

    def report_totals(self, severity=None, zeros=False):
        """
        Return list of dicts with total numbers of tests completed with
        different marks. Each list item corresponds to one of marks:
        CRASHED, FAILED, SKIPPED, SUCCEEDED. Items are put into the list
        in the decreasing order of severity level (i.e., from CRASHED
        downto SUCCEEDED, as shown above).

        Items for marks having severity level lower than specified with
        `severity` are omitted. Left `severity=None` to include all
        levels into the report.

        By default levels which totalized to zero are not included into
        the report. To include them all set `zeros=True`.

        Each item in the returned list includes fields:
        - `mark` -- numeric code of the mark, CRASHED=3, FAILED=2,
                SKIPPED=1, SUCCEEDED=0
        - `verb` -- string representing the mark: 'crashed', 'failed',
                'skipped', 'succeeded'
        - `num` -- total number of tests completed with the given mark

        To concatenate results one may use expression:
            ("Totals: " + ', '.join(
                map(lambda item: "{num} {verb}".format(**item),
                    my_test.report_totals(severity, zeros))))

        For `severity=MethodTest.SKIPPED` it will give something like:
            "Totals: 5 failed, 3 skipped"

        And if additionally `zeros=True`, it will give:
            "Totals: 0 crashed, 5 failed, 3 skipped"

        To get the total number of tests in the suite use:
            len(my_test.statement)
        """

        return filter(lambda tot: zeros or tot['num'] > 0, map(
            lambda mark: dict(mark=mark,
                              verb=MethodTest.MARKS[mark]['verb'],
                              num=len(self._slice_statement(mark))),
            reversed(MethodTest._filter_marks(severity))))

    def _slice_statement(self, mark):
        return filter(lambda rec: rec['mark'] == mark, self.statement)

    @staticmethod
    def _filter_marks(severity):
        return filter(lambda mark: mark >= severity,
                      MethodTest.MARKS.viewkeys())

    def report_mark(self):
        """
        Report the overall test suite mark calculated as the maximum
        over all individual test marks.

        If all tests succeeded, the overall mark is SUCCEEDED=0. If at
        least one test was skipped but no tests failed or crashed, the
        overall mark is SKIPPED=1. If at least one test failed but no
        tests crashed, the overall mark is FAILED=2. And if at least one
        test crashed, the overall mark is CRASHED=3.
        """

        return max(map(lambda rec: rec['mark'], self.statement))

    def report_cli(self):
        """
        Make aggregated report for printing to console (command line
        interface). The report is returned as a single text string with
        necessary line-endings fully ready for printing.
        """

        report = ["Test {}.{}:".format(self.method.im_class.__name__,
                                       self.method.im_func.__name__)]

        if self.report_mark() == MethodTest.SUCCEEDED:
            brief = "{} {}".format(
                len(self.statement),
                MethodTest.MARKS[MethodTest.SUCCEEDED]['verb'])
        else:
            brief = "{} (of {})".format(
                ', '.join(map(lambda item: "{num} {verb}".format(**item),
                              self.report_totals(MethodTest.SKIPPED))),
                len(self.statement))

        report.append("{} = {}".format(self.report_bar(), brief))

        map(lambda rec: report.append(
            ": {} = {}{}".format(rec['tid'],
                                 MethodTest.MARKS[rec['mark']]['verb'],
                                 ", " + rec['msg'] if rec['msg'] else "")),
            self.report_statement(severity=MethodTest.SKIPPED))

        return '\n'.join(report)

    def harness(self, test):
        """
        Create quasi-virtual global environment for the tested method
        and its sandbox, run the method and check the final state of the
        virtual environment.

        If the actual result of the test run differs from the expected
        as it is described in the test, the detailed diagnostic message
        is returned. If they match, None is returned.

        Virtual environment includes two things:
        - global logger which is referenced with `log`
        - exceptions catching and handling

        Virtual environment intercepts all messages logged and exception
        raised by the tested method. After the method finished, the set
        of logged messages and the raised exception is checked against
        `logs` and `raises` items specified in the test description. The
        `logs` item must be a list of messages fabricated with `error`,
        `warn` and `info` functions of this framework. The `raises` item
        must be assigned with the expected exception object.
        """

        log = MethodTestLogger()

        try:
            try:
                module = modules[self.method.im_class.__module__]
                log_saved = module.log
                module.log = log
            except:
                pass

            test_raises = test.get('raises')

            adapter = MethodTestAdapter(self.method, test).setup()

            try:
                adapter.run()

            except Exception as e:
                if not test_raises:
                    return "unexpected exception " + repr(e)

                if not (type(e) is type(test_raises)
                        and repr(e) == repr(test_raises)):
                    return ("different exception {}, expected {}"
                            .format(repr(e), repr(test_raises)))
            else:
                if test_raises:
                    return "missed exception, expected " + repr(test_raises)

            mismatch = adapter.check()

            if mismatch:
                return mismatch

            if 'logs' in test and log.logged != test['logs']:
                return ("different log [{}], expected [{}]"
                        .format(', '.join(log.logged),
                                ', '.join(test['logs'])))

            return None  # Success

        finally:
            try:
                module.log = log_saved
            except:
                pass


class MethodTestAdapter(object):
    """
    Provide a properly initialized sandbox for the tested method, bind
    the initially unbound method to the sandbox instance and run it,
    then check the output.

    Test adapter is created from the scratch for each test in the suite.
    Theoretically it fully isolates tests from each other. Crosstalk is
    still possible as soon as the tested method potentially may
    establish its own bindings to the environment which is not
    virtualized in this framework.

    Mutable objects may be used in test description. Adapter creates
    full copies of them (using deepcopy) when initializing sandbox and
    running the tested method.

    Test description includes:
    - `mocks` -- dictionary of mocks to be installed in the sandbox
    - `init_args`, `init_kwargs` -- positional and named arguments to be
            passed to `__init__`-mock if such is introduced with `mocks`
    - `setup` -- dictionary of attributes to be installed in the sandbox
    - `args`, `kwargs` -- positional and named arguments to be passed to
            the tested method
    - `returns` -- value expected to be returned by the tested method
    - `final` -- dictionary of attribute values expected in the sandbox
            after the tested method run

    All the listed items are optional in general. Test description may
    contain other items with different keys.
    """

    def __init__(self, method, test=None):
        """
        Initialize a test adapter and bind it to the given method and
        test description.
        """

        self.method = method
        self.test = test if test else {}

    def setup(self):
        """
        Create and initialize a sandbox for the method to be tested.

        Sandbox is an instance of the artificial sandbox-class which is
        a direct derivative of the class owning the method to be tested.

        Sandbox is used for two main purposes:
        - it hides native `__init__` and `__del__` methods of the tested
                class, so they are not called when an instance of the
                tested class is created or deleted (otherwise they might
                produce side-effects)
        - it installs mocks for particular methods of the tested class
                if such are specified with `mocks` in the test
                description

        Note that mocks may be provided also for `__init__` and
        `__del__` methods. In such case they will be called on sandbox
        initialization/deletion, and the `__init__`-mock will be called
        with arguments given with `init_args`, `init_kwargs` in the test
        description. However normally such mocks should not be used.

        When a sandbox is created, its dictionary is updated with
        `setup` profile specified in the test descriptor. This is used
        to force sandbox to appropriate state from which the tested
        method shall be run.

        This method returns its `self` to allow chained calls. It may be
        helpful to call it right after `__init__` and save the newly
        created class instance reference.
        """

        stub_func = lambda self, *args, **kwargs: None
        sandbox_dict = dict(__init__=stub_func, __del__=stub_func)
        sandbox_dict.update(deepcopy(self.test.get('mocks', {})))

        method_class = self.method.im_class
        sandbox_name = method_class.__name__
        sandbox_base = (method_class,)
        sandbox_class = type(sandbox_name, sandbox_base, sandbox_dict)

        self.sandbox = sandbox_class(
            *deepcopy(self.test.get('init_args', ())),
            **deepcopy(self.test.get('init_kwargs', {})))

        self.sandbox.__dict__.update(deepcopy(self.test.get('setup', {})))

        return self

    def run(self):
        """
        Run the method under test in the configured sandbox and save the
        returned value.

        Method is called with the following arguments:
        - `self` -- this is assigned with the created sandbox
        - `args`, `kwargs` -- positional and named arguments as they are
                specified in the test description

        This method returns its `self` to allow chained calls. It may be
        helpful to call it right after `setup` or in front of `check`.
        """

        self.returns = self.method(
            self.sandbox, *deepcopy(self.test.get('args', ())),
            **deepcopy(self.test.get('kwargs', {})))

        return self

    def check(self):
        """
        Check the value returned by the tested method and the final
        state of the sandbox.

        The returned value and the sandbox state are verified against
        the expected patterns if such are specified in the test
        description, namely `returns` and `final`. The first one is an
        arbitrary type object or None, and the second is a dictionary
        similar to `setup` described in the docstring to `setup` method.

        The final state is checked for absolute match. If there are
        attributes in the sandbox dictionary which are not listed in the
        `final` set, the state is considered invalid.

        Returned value and the sandbox attributes are compared by value.
        This framework is not able to check equality of references to
        objects, it checks quality of objects.

        On match this function returns None. On mismatch it returns
        detailed diagnostic message.
        """

        if 'returns' in self.test and self.returns != self.test['returns']:
            return ("invalid returns={!r}, expected {!r}"
                    .format(self.returns, self.test['returns']))

        if 'final' in self.test:
            actual = self.sandbox.__dict__.viewkeys()
            expected = self.test['final'].viewkeys()

            if actual != expected:
                return ("invalid attributes set [{}], expected [{}], "
                        "excessive [{}], missed [{}]"
                        .format(', '.join(sorted(actual)),
                                ', '.join(sorted(expected)),
                                ', '.join(sorted(actual - expected)),
                                ', '.join(sorted(expected - actual))))

            actual = self.sandbox.__dict__
            expected = self.test['final']

            for attr in sorted(expected):
                if actual[attr] != expected[attr]:
                    shorten = lambda s, n: ("{}...{} ({})"
                                            .format(s[:n], s[-1], len(s))
                                            if len(s) > n else s)
                    return ("invalid attribute {}={}, expected {}"
                            .format(attr, shorten(repr(actual[attr]), 100),
                                    shorten(repr(expected[attr]), 100)))

        return None  # Success


class MethodTestLogger(object):

    def __init__(self):
        self.clear()

    def error(self, msg):
        self.logged.append(error(msg))

    def warn(self, msg):
        self.logged.append(warn(msg))

    def info(self, msg):
        self.logged.append(info(msg))

    def clear(self):
        self.logged = []


def error(msg):
    return 'E: ' + msg


def warn(msg):
    return 'W: ' + msg


def info(msg):
    return 'I: ' + msg
