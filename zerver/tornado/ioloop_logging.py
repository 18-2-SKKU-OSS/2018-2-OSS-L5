import logging
import select
import time
from typing import Any, Dict, List, Tuple

from django.conf import settings
from tornado.ioloop import IOLoop, PollIOLoop

# There isn't a good way to get at what the underlying poll implementation
# will be without actually constructing an IOLoop, so we just assume it will
# be epoll.
orig_poll_impl = select.epoll

# This is used for a somewhat hacky way of passing the port number
# into this early-initialized module.
logging_data = {}  # type: Dict[str, str]

class InstrumentedPollIOLoop(PollIOLoop):
    def initialize(self, **kwargs):  # type: ignore # TODO investigate likely buggy monkey patching here
        super().initialize(impl=InstrumentedPoll(), **kwargs)

def instrument_tornado_ioloop() -> None:
    IOLoop.configure(InstrumentedPollIOLoop)

# A hack to keep track of how much time we spend working, versus sleeping in
# the event loop.
#
# Creating a new event loop instance with a custom impl object fails (events
# don't get processed), so instead we modify the ioloop module variable holding
# the default poll implementation.  We need to do this before any Tornado code
# runs that might instantiate the default event loop.

class InstrumentedPoll:
    def __init__(self) -> None:
        self._underlying = orig_poll_impl()
        self._times = []  # type: List[Tuple[float, float]]
        self._last_print = 0.0

    # Python won't let us subclass e.g. select.epoll, so instead
    # we proxy every method.  __getattr__ handles anything we
    # don't define elsewhere.
    def __getattr__(self, name: str) -> Any:
        return getattr(self._underlying, name)

    # Call the underlying poll method, and report timing data.
    def poll(self, timeout: float) -> Any:

        # Avoid accumulating a bunch of insignificant data points
        # from short timeouts.
        if timeout < 1e-3:
            return self._underlying.poll(timeout)

        # Record start and end times for the underlying poll
        t0 = time.time()
        result = self._underlying.poll(timeout)
        t1 = time.time()

        # Log this datapoint and restrict our log to the past minute
        self._times.append((t0, t1))
        while self._times and self._times[0][0] < t1 - 60:
            self._times.pop(0)

        # Report (at most once every 5s) the percentage of time spent
        # outside poll
        if self._times and t1 - self._last_print >= 5:
            total = t1 - self._times[0][0]
            in_poll = sum(b-a for a, b in self._times)
            if total > 0:
                percent_busy = 100 * (1 - in_poll / total)
                if settings.PRODUCTION:
                    logging.info('Tornado %s %5.1f%% busy over the past %4.1f seconds'
                                 % (logging_data.get('port', 'unknown'), percent_busy, total))
                    self._last_print = t1

        return result
