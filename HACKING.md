# opie Style Commandments

opie follows the same style Commandments as upstream OpenStack Nova, so the
following reference pacge must be kept under the pillow:

http://docs.openstack.org/developer/hacking/

# Testing

## Creating Unit Tests

For every new feature, unit tests should be created that both test and
(implicitly) document the usage of said feature. If submitting a patch for a
bug that had no unit test, a new passing unit test should be added. If a
submitted bug fix does have a unit test, be sure to add a new one that fails
without the patch and passes with the patch.

## Running Tests

The testing system is based on a combination of tox and testr. The canonical
approach to running tests is to simply run the command `tox`. This will
create virtual environments, populate them with dependencies and run all of
the tests that OpenStack CI systems run. Behind the scenes, tox is running
`testr run --parallel`, but is set up such that you can supply any additional
testr arguments that are needed to tox. For example, you can run:
`tox -- --analyze-isolation` to cause tox to tell testr to add
--analyze-isolation to its argument list.

To run a single or restricted set of tests, pass a regex that matches the class
name containing the tests as an extra `tox` argument; e.g. `tox --
OpieFilterSchedulerTestCase` (note the double-hypen) will test all the Filter
Scheduler tests from `opie/tests/test_scheduler.py`;
`-- OpieFilterSchedulerTestCase.test_detect_preemptible_empty` would run just
that test, and `-- OpieFilterSchedulerTestCase|PreemptibleCountWeigherTestCase`
would run tests from both classes.

It is also possible to run the tests inside of a virtual environment
you have created, or it is possible that you have all of the dependencies
installed locally already. In this case, you can interact with the testr
command directly. Running `testr run` will run the entire test suite. `testr
run --parallel` will run it in parallel (this is the default incantation tox
uses.) More information about testr can be found at:
http://wiki.openstack.org/testr

# Docs

Normal Sphinx docs can be built via the setuptools `build_sphinx` command. To
do this via `tox`, simply run `tox -e docs`,
which will cause a virtualenv with all of the needed dependencies to be
created and then inside of the virtualenv, the docs will be created and
put into doc/build/html.
