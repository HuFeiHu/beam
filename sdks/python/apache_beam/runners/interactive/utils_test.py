#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from __future__ import absolute_import

import logging
import sys
import unittest

import numpy as np
import pandas as pd

from apache_beam.runners.interactive import interactive_environment as ie
from apache_beam.runners.interactive import utils
from apache_beam.utils.windowed_value import WindowedValue

# TODO(BEAM-8288): clean up the work-around of nose tests using Python2 without
# unittest.mock module.
try:
  from unittest.mock import patch
except ImportError:
  from mock import patch


class ParseToDataframeTest(unittest.TestCase):
  def test_parse_windowedvalue(self):
    """Tests that WindowedValues are supported but not present.
    """
    from apache_beam.transforms.window import GlobalWindow

    els = [
        WindowedValue(('a', 2), 1, [GlobalWindow()]),
        WindowedValue(('b', 3), 1, [GlobalWindow()])
    ]

    actual_df = utils.elements_to_df(els, include_window_info=False)
    expected_df = pd.DataFrame([['a', 2], ['b', 3]], columns=[0, 1])
    # check_like so that ordering of indices doesn't matter.
    pd.testing.assert_frame_equal(actual_df, expected_df, check_like=True)

  def test_parse_windowedvalue_with_window_info(self):
    """Tests that WindowedValues are supported and have their own columns.
    """
    from apache_beam.transforms.window import GlobalWindow

    els = [
        WindowedValue(('a', 2), 1, [GlobalWindow()]),
        WindowedValue(('b', 3), 1, [GlobalWindow()])
    ]

    actual_df = utils.elements_to_df(els, include_window_info=True)
    expected_df = pd.DataFrame(
        [['a', 2, int(1e6), els[0].windows, els[0].pane_info],
         ['b', 3, int(1e6), els[1].windows, els[1].pane_info]],
        columns=[0, 1, 'event_time', 'windows', 'pane_info'])
    # check_like so that ordering of indices doesn't matter.
    pd.testing.assert_frame_equal(actual_df, expected_df, check_like=True)

  def test_parse_windowedvalue_with_dicts(self):
    """Tests that dicts play well with WindowedValues.
    """
    from apache_beam.transforms.window import GlobalWindow

    els = [
        WindowedValue({
            'b': 2, 'd': 4
        }, 1, [GlobalWindow()]),
        WindowedValue({
            'a': 1, 'b': 2, 'c': 3
        }, 1, [GlobalWindow()])
    ]

    actual_df = utils.elements_to_df(els, include_window_info=True)
    expected_df = pd.DataFrame(
        [[np.nan, 2, np.nan, 4, int(1e6), els[0].windows, els[0].pane_info],
         [1, 2, 3, np.nan, int(1e6), els[1].windows, els[1].pane_info]],
        columns=['a', 'b', 'c', 'd', 'event_time', 'windows', 'pane_info'])
    # check_like so that ordering of indices doesn't matter.
    pd.testing.assert_frame_equal(actual_df, expected_df, check_like=True)


@unittest.skipIf(
    not ie.current_env().is_interactive_ready,
    '[interactive] dependency is not installed.')
@unittest.skipIf(
    sys.version_info < (3, 6), 'The tests require at least Python 3.6 to work.')
class IPythonLogHandlerTest(unittest.TestCase):
  def setUp(self):
    utils.register_ipython_log_handler()
    self._interactive_root_logger = logging.getLogger(
        'apache_beam.runners.interactive')

  def test_ipython_log_handler_not_double_registered(self):
    utils.register_ipython_log_handler()
    ipython_log_handlers = list(
        filter(
            lambda x: isinstance(x, utils.IPythonLogHandler),
            [handler for handler in self._interactive_root_logger.handlers]))
    self.assertEqual(1, len(ipython_log_handlers))

  @patch('apache_beam.runners.interactive.utils.IPythonLogHandler.emit')
  def test_default_logging_level_is_info(self, mock_emit):
    # By default the logging level of loggers and log handlers are NOTSET. Also,
    # the propagation is default to true for all loggers. In this scenario, all
    # loggings from child loggers will be propagated to the interactive "root"
    # logger which is set to INFO level that gets handled by the sole log
    # handler IPythonLogHandler which is set to NOTSET. The effect will be
    # everything >= info level will be logged through IPython.core.display to
    # all frontends connected to current kernel.
    dummy_logger = logging.getLogger('apache_beam.runners.interactive.dummy1')
    dummy_logger.info('info')
    mock_emit.assert_called_once()
    dummy_logger.debug('debug')
    # Emit is not called, so it's still called once.
    mock_emit.assert_called_once()

  @patch('apache_beam.runners.interactive.utils.IPythonLogHandler.emit')
  def test_child_module_logger_can_override_logging_level(self, mock_emit):
    # When a child logger's logging level is configured to something that is not
    # NOTSET, it takes back the logging control from the interactive "root"
    # logger by not propagating anything.
    dummy_logger = logging.getLogger('apache_beam.runners.interactive.dummy2')
    dummy_logger.setLevel(logging.DEBUG)
    mock_emit.assert_not_called()
    dummy_logger.debug('debug')
    # Because the dummy child logger is configured to log at DEBUG level, it
    # now propagates DEBUG loggings to the interactive "root" logger.
    mock_emit.assert_called_once()
    # When the dummy child logger is configured to log at CRITICAL level, it
    # will only propagate CRITICAL loggings to the interactive "root" logger.
    dummy_logger.setLevel(logging.CRITICAL)
    # Error loggings will not be handled now.
    dummy_logger.error('error')
    # Emit is not called, so it's still called once.
    mock_emit.assert_called_once()


if __name__ == '__main__':
  unittest.main()
