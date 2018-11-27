/*

This test module actually tests our test code, particularly zblueslip, and
it is intended to demonstrate how to use zblueslip (as well as, of course,
verify that it works as advertised).

What is zblueslip?

    The zblueslip test module behaves like blueslip at a very surface level,
    and it allows you to test code that uses actual blueslip and add some
    custom validation for checking that only particular errors and warnings are
    thrown by our test modules.

The code we are testing lives here:

    https://github.com/zulip/zulip/blob/master/frontend_tests/zjsunit/zblueslip.js

Read the following contents for an overview of how zblueslip works. Also take a
look at `node_tests/people_errors.js` for actual usage of this module.
*/


// The first thing we do to use zblueslip is patch our global namespace
// with zblueslip as follows.  This call gives us our own instance of a
// zblueslip stub variable.
set_global('blueslip', global.make_zblueslip());

// Aditionally, you can specify which functions you want to test for/ignore.
// By default, we ignore debug, log and info. To test for debug, for example, do:
// set_global('blueslip', global.make_zblueslip({debug: true}));
// Similarly, you can ignore tests for errors by passing {debug: true, error: false}.

run_test('basics', () => {
    // Let's create a sample piece of code to test:
    function throw_an_error() {
        blueslip.error('world');
    }

    // Let's add an error that we are expecting from the module.
    // The function 'set_test_data' pushes the expected error message to the array
    // of messages expected for that log type; here, 'error'.
    blueslip.set_test_data('error', 'hello');
    // Since the error 'world' is not being expected, blueslip will
    // throw an error.
    assert.throws(throw_an_error);
    // zblueslip logs all the calls made to it, and they can be used in asserts like:
    assert.equal(blueslip.get_test_logs('error').length, 1);

    // Now, let's add our error to the list of expected errors.
    blueslip.set_test_data('error', 'world');
    // This time, blueslip will just log the error, which is
    // being verified by the assert call on the length of the log.
    // We can also check for which specific error was logged, but since
    // our sample space is just 1 expected error, we are sure that
    // only that error could have been logged, and others would raise
    // an error, aborting the test.
    throw_an_error();
    assert.equal(blueslip.get_test_logs('error').length, 2);

    // Let's clear the array of valid errors as well as the log. Now, all errors
    // should be thrown directly by blueslip.
    blueslip.clear_test_data();
    assert.throws(throw_an_error);
    assert.equal(blueslip.get_test_logs('error').length, 1);
    blueslip.clear_test_data();

    // Let's repeat the above procedue with warnings. Unlike errors,
    // warnings shoudln't stop the code execution, and thus, the
    // behaviour is slightly different.

    function throw_a_warning() {
        blueslip.warn('world');
    }

    // Populate one valid value, and test with an invalid value.
    // This should throw an error, and we'll assert it was thrown by zblueslip.
    blueslip.set_test_data('warn', 'hello');
    assert.throws(throw_a_warning);
    blueslip.clear_test_data();

    // Now, let's add our warning to the list of expected warnings.
    // This time, we shouldn't throw an error. However, to confirm that we
    // indeed had logged a warning, we can check the length of the warning logs
    blueslip.set_test_data('warn', 'world');
    throw_a_warning();
    assert.equal(blueslip.get_test_logs('warn').length, 1);
    blueslip.clear_test_data();

    // Finally, let's check the wrap_function feature which allows logging
    // of errors in function calls. We can use it as follows:
    const original_function = () => {
        return 'hello';
    };
    const wrapped_function = blueslip.wrap_function(original_function);
    assert.equal(original_function(), wrapped_function());
});
