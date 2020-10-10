# vim: sw=4:ts=4:et:cc=120

import datetime
import os, os.path
import shutil
import tempfile
import threading

import saq
from saq.submission import Submission
from saq.collectors.hunter import HunterCollector, HuntManager, Hunt, open_hunt_db
from saq.collectors.test import CollectorBaseTestCase
from saq.constants import *
from saq.service import *
from saq.test import *
from saq.util import *

class TestHunt(Hunt):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.executed = False

    def execute(self):
        logging.info(f"unit test execute marker: {self}")
        self.executed = True
        return [ Submission(
            description='test',
            analysis_mode=ANALYSIS_MODE_CORRELATION,
            tool='test_tool',
            tool_instance='test_tool_instance',
            type='test_type') ]

    def cancel(self):
        pass

def default_hunt(manager, enabled=True, name='test_hunt', description='Test Hunt', alert_type='test - alert',
                 frequency=create_timedelta('00:10'), tags=[ 'test_tag' ]):
    hunt = TestHunt(enabled=enabled, name=name, description=description,
                    alert_type=alert_type, frequency=frequency, tags=tags)
    hunt.manager = manager
    return hunt

class HunterBaseTestCase(CollectorBaseTestCase):
    def setUp(self, *args, **kwargs):
        super().setUp(*args, **kwargs)
    
        # delete all the existing hunt types
        hunt_type_sections = [_ for _ in saq.CONFIG.sections() if _.startswith('hunt_type_')]
        for hunt_type_section in hunt_type_sections:
            del saq.CONFIG[hunt_type_section]

        # copy the hunts into a temporary directory
        self.temp_rules_dir = tempfile.mkdtemp(dir=saq.TEMP_DIR)
        self.temp_rules_dir = os.path.join(self.temp_rules_dir, 'rules')
        shutil.copytree('hunts/test/generic', self.temp_rules_dir)

    def clear_temp_rules_dir(self):
        for file_name in os.listdir(self.temp_rules_dir):
            os.remove(os.path.join(self.temp_rules_dir, file_name))

    def manager_kwargs(self):
        return { 'collector': HunterCollector(),
                 'hunt_type': 'test',
                 'rule_dirs': [self.temp_rules_dir,],
                 'hunt_cls': TestHunt,
                 'concurrency_limit': 1,
                 'persistence_dir': os.path.join(saq.DATA_DIR, saq.CONFIG['collection']['persistence_dir']),
                 'update_frequency': 60,
                 'config': {}}

class TestCase(HunterBaseTestCase):
    def setUp(self, *args, **kwargs):
        super().setUp(*args, **kwargs)

        saq.CONFIG.add_section('hunt_type_test')
        s = saq.CONFIG['hunt_type_test']
        s['module'] = 'saq.collectors.test_hunter'
        s['class'] = 'TestHunt'
        s['rule_dirs'] = self.temp_rules_dir
        s['concurrency_limit'] = '1'

    def tearDown(self, *args, **kwargs):
        super().tearDown(*args, **kwargs)
        shutil.rmtree(self.temp_rules_dir)

    def test_start_stop(self):
        collector = HunterCollector()
        collector.start_service(threaded=True)
        wait_for_log_count('started Hunt Manager(test)', 1)
        collector.stop_service()
        collector.wait_service()

    def test_hunt_persistence(self):
        hunter = HuntManager(**self.manager_kwargs())
        hunter.add_hunt(default_hunt(manager=hunter))
        hunter.hunts[0].last_executed_time = datetime.datetime(2019, 12, 10, 8, 21, 13)
        
        with open_hunt_db(hunter.hunts[0].type) as db:
            c = db.cursor()
            c.execute("""SELECT last_executed_time FROM hunt WHERE hunt_name = ?""", (hunter.hunts[0].name,))
            row = c.fetchone()
            self.assertIsNotNone(row)
            last_executed_time = row[0]
            self.assertTrue(isinstance(last_executed_time, datetime.datetime))
            self.assertEquals(last_executed_time.year, 2019)
            self.assertEquals(last_executed_time.month, 12)
            self.assertEquals(last_executed_time.day, 10)
            self.assertEquals(last_executed_time.hour, 8)
            self.assertEquals(last_executed_time.minute, 21)
            self.assertEquals(last_executed_time.second, 13)
        
    def test_add_hunt(self):
        hunter = HuntManager(**self.manager_kwargs())
        hunter.add_hunt(default_hunt(manager=hunter))
        self.assertEquals(len(hunter.hunts), 1)

    def test_add_duplicate_hunt(self):
        # should not be allowed to add a hunt that already exists
        hunter = HuntManager(**self.manager_kwargs())
        hunter.add_hunt(default_hunt(manager=hunter))
        with self.assertRaises(KeyError):
            hunter.add_hunt(default_hunt(manager=hunter))

    def test_remove_hunt(self):
        hunter = HuntManager(**self.manager_kwargs())
        hunt = hunter.add_hunt(default_hunt(manager=hunter))
        removed = hunter.remove_hunt(hunt)
        self.assertEquals(hunt.name, removed.name)
        self.assertEquals(len(hunter.hunts), 0)

    def test_hunt_order(self):
        hunter = HuntManager(**self.manager_kwargs())
        # test initial hunt order
        # these are added in the wrong order but the should be sorted when we access them
        hunter.add_hunt(default_hunt(manager=hunter, name='test_hunt_3', frequency=create_timedelta('00:30')))
        hunter.add_hunt(default_hunt(manager=hunter, name='test_hunt_2', frequency=create_timedelta('00:20')))
        hunter.add_hunt(default_hunt(manager=hunter, name='test_hunt_1', frequency=create_timedelta('00:10')))

        # assume we've executed all of these hunts
        for hunt in hunter.hunts:
            hunt.last_executed_time = datetime.datetime.now()

        # now they should be in this order
        self.assertEquals(hunter.hunts[0].name, 'test_hunt_1')
        self.assertEquals(hunter.hunts[1].name, 'test_hunt_2')
        self.assertEquals(hunter.hunts[2].name, 'test_hunt_3')

    def test_hunt_execution(self):
        collector = HunterCollector()
        collector.start_service(threaded=True)
        # testing that the execution order works
        wait_for_log_count('unit test execute marker: Hunt(Test 2[test])', 4)
        self.assertEquals(log_count('unit test execute marker: Hunt(unit_test_1[test])'), 1)
        self.assertTrue(log_count('next hunt is Hunt(Test 2[test])') > 0)
        collector.stop_service()
        collector.wait_service()

    def test_load_hunts(self):
        hunter = HuntManager(**self.manager_kwargs())
        hunter.load_hunts_from_config()
        for hunt in hunter.hunts:
            hunt.manager = hunter
        self.assertEquals(len(hunter.hunts), 2)
        self.assertTrue(isinstance(hunter.hunts[0], TestHunt))
        self.assertTrue(isinstance(hunter.hunts[1], TestHunt))

        for hunt in hunter.hunts:
            hunt.last_executed_time = datetime.datetime.now()

        self.assertTrue(hunter.hunts[1].enabled)
        self.assertEquals(hunter.hunts[1].name, 'unit_test_1')
        self.assertEquals(hunter.hunts[1].description, 'Unit Test Description 1')
        self.assertEquals(hunter.hunts[1].type, 'test')
        self.assertEquals(hunter.hunts[1].alert_type, 'test - alert')
        self.assertEquals(hunter.hunts[1].analysis_mode, ANALYSIS_MODE_CORRELATION)
        self.assertTrue(isinstance(hunter.hunts[1].frequency, datetime.timedelta))
        self.assertEquals(hunter.hunts[1].tags, ['tag1', 'tag2'])

        self.assertTrue(hunter.hunts[0].enabled)
        # the second one is missing the name so the name is auto generated
        self.assertEquals(hunter.hunts[0].name, 'Test 2')
        self.assertEquals(hunter.hunts[0].description, 'Unit Test Description 2')
        self.assertEquals(hunter.hunts[0].type, 'test')
        # the second one is missing the alert_type so this is auto generated
        self.assertEquals(hunter.hunts[0].alert_type, 'hunter - test')
        self.assertEquals(hunter.hunts[0].analysis_mode, ANALYSIS_MODE_ANALYSIS)
        self.assertTrue(isinstance(hunter.hunts[0].frequency, datetime.timedelta))
        self.assertEquals(hunter.hunts[0].tags, ['tag1', 'tag2'])

    def test_fix_invalid_hunt(self):
        failed_ini_path = os.path.join(self.temp_rules_dir, 'test_3.ini')
        with open(failed_ini_path, 'w') as fp:
            fp.write("""
[rule]
enabled = yes
name = unit_test_3
description = Unit Test Description 3
type = test
alert_type = test - alert
;frequency = 00:00:01 <-- missing frequency
tags = tag1, tag2 """)

        hunter = HuntManager(**self.manager_kwargs())
        hunter.load_hunts_from_config()
        self.assertEquals(len(hunter.hunts), 2)
        self.assertEquals(len(hunter.failed_ini_files), 1)
        self.assertTrue(failed_ini_path in hunter.failed_ini_files)
        self.assertEquals(hunter.failed_ini_files[failed_ini_path], os.path.getmtime(failed_ini_path))

        self.assertFalse(hunter.reload_hunts_flag)
        hunter.check_hunts()
        self.assertFalse(hunter.reload_hunts_flag)

        with open(failed_ini_path, 'w') as fp:
            fp.write("""
[rule]
enabled = yes
name = unit_test_3 
description = Unit Test Description 3
type = test
alert_type = test - alert
frequency = 00:00:01
tags = tag1, tag2 """)

        hunter.check_hunts()
        self.assertTrue(hunter.reload_hunts_flag)
        hunter.reload_hunts()
        self.assertEquals(len(hunter.hunts), 3)
        self.assertEquals(len(hunter.failed_ini_files), 0)

    def test_load_hunts_wrong_type(self):
        shutil.rmtree(self.temp_rules_dir)
        os.mkdir(self.temp_rules_dir)
        with open(os.path.join(self.temp_rules_dir, 'hunt_invalid.ini'), 'w') as fp:
            fp.write("""
[rule]
enabled = yes
name = test_wrong_type
description = Testing Wrong Type
type = unknown
alert_type = test - alert
frequency = 00:00:01
tags = tag1, tag2 """)


        with open(os.path.join(self.temp_rules_dir, 'hunt_valid.ini'), 'w') as fp:
            fp.write("""
[rule]
enabled = yes
name = unit_test_3 
description = Unit Test Description 3
type = test
alert_type = test - alert
frequency = 00:00:01
tags = tag1, tag2 """)

        hunter = HuntManager(**self.manager_kwargs())
        hunter.load_hunts_from_config()
        for hunt in hunter.hunts:
            hunt.manager = hunter

        self.assertEquals(len(hunter.hunts), 1)
        self.assertFalse(hunter.reload_hunts_flag)

        # nothing has changed so this should still be False
        hunter.check_hunts()
        self.assertFalse(hunter.reload_hunts_flag)

    def test_hunt_disabled(self):
        hunter = HuntManager(**self.manager_kwargs())
        hunter.load_hunts_from_config()
        hunter.hunts[0].enabled = True
        hunter.hunts[1].enabled = True

        self.assertTrue(all([not hunt.executed for hunt in hunter.hunts]))
        hunter.execute()
        hunter.manager_control_event.set()
        hunter.wait_control_event.set()
        hunter.wait()
        self.assertTrue(all([hunt.executed for hunt in hunter.hunts]))

        hunter = HuntManager(**self.manager_kwargs())
        hunter.load_hunts_from_config()
        hunter.hunts[0].enabled = False
        hunter.hunts[1].enabled = False

        self.assertTrue(all([not hunt.executed for hunt in hunter.hunts]))
        hunter.execute()
        hunter.execute()
        hunter.manager_control_event.set()
        hunter.wait_control_event.set()
        hunter.wait()
        self.assertTrue(all([not hunt.executed for hunt in hunter.hunts]))

    def test_reload_hunts_on_sighup(self):
        collector = HunterCollector()
        collector.start_service(threaded=True)
        wait_for_log_count('loaded Hunt(unit_test_1[test]) from', 1)
        wait_for_log_count('loaded Hunt(Test 2[test]) from', 1)
        os.kill(os.getpid(), signal.SIGHUP)
        wait_for_log_count('received signal to reload hunts', 1)
        wait_for_log_count('loaded Hunt(unit_test_1[test]) from', 2)
        wait_for_log_count('loaded Hunt(Test 2[test]) from', 2)
        collector.stop_service()
        collector.wait_service()

    def test_reload_hunts_on_ini_modified(self):
        saq.CONFIG['service_hunter']['update_frequency'] = '1'
        collector = HunterCollector()
        collector.start_service(threaded=True)
        wait_for_log_count('loaded Hunt(unit_test_1[test]) from', 1)
        wait_for_log_count('loaded Hunt(Test 2[test]) from', 1)
        with open(os.path.join(self.temp_rules_dir, 'test_1.ini'), 'a') as fp:
            fp.write('\n\n; modified')

        wait_for_log_count('detected modification to', 1, 5)
        wait_for_log_count('loaded Hunt(unit_test_1[test]) from', 2)
        wait_for_log_count('loaded Hunt(Test 2[test]) from', 2)
        collector.stop_service()
        collector.wait_service()

    def test_reload_hunts_on_deleted(self):
        saq.CONFIG['service_hunter']['update_frequency'] = '1'
        collector = HunterCollector()
        collector.start_service(threaded=True)
        wait_for_log_count('loaded Hunt(unit_test_1[test]) from', 1)
        wait_for_log_count('loaded Hunt(Test 2[test]) from', 1)
        os.remove(os.path.join(self.temp_rules_dir, 'test_1.ini'))
        wait_for_log_count('detected modification to', 1, 5)
        wait_for_log_count('loaded Hunt(Test 2[test]) from', 2)
        self.assertTrue(log_count('loaded Hunt(unit_test_1[test]) from') == 1)
        collector.stop_service()
        collector.wait_service()

    def test_reload_hunts_on_new(self):
        saq.CONFIG['service_hunter']['update_frequency'] = '1'
        collector = HunterCollector()
        collector.start_service(threaded=True)
        wait_for_log_count('loaded Hunt(unit_test_1[test]) from', 1)
        wait_for_log_count('loaded Hunt(Test 2[test]) from', 1)
        with open(os.path.join(self.temp_rules_dir, 'test_3.ini'), 'a') as fp:
            fp.write("""
[rule]
enabled = yes
name = unit_test_3
description = Unit Test Description 3
type = test
alert_type = test - alert
frequency = 00:00:10
tags = tag1, tag2""")

        wait_for_log_count('detected new hunt ini', 1, 5)
        wait_for_log_count('loaded Hunt(unit_test_1[test]) from', 2)
        wait_for_log_count('loaded Hunt(Test 2[test]) from', 2)
        wait_for_log_count('loaded Hunt(unit_test_3[test]) from', 1)
        collector.stop_service()
        collector.wait_service()

    # TODO test the semaphore locking

    def test_valid_cron_schedule(self):
        self.clear_temp_rules_dir()
        with open(os.path.join(self.temp_rules_dir, 'test_1.ini'), 'a') as fp:
            fp.write("""
[rule]
enabled = yes
name = unit_test_1
description = Unit Test Description 1
type = test
alert_type = test - alert
frequency = */1 * * * *
tags = tag1, tag2""")

        hunter = HuntManager(**self.manager_kwargs())
        hunter.load_hunts_from_config()
        self.assertEquals(len(hunter.hunts), 1)
        self.assertTrue(isinstance(hunter.hunts[0], TestHunt))
        self.assertIsNone(hunter.hunts[0].frequency)
        self.assertEquals(hunter.hunts[0].cron_schedule, '*/1 * * * *')

    def test_invalid_cron_schedule(self):
        self.clear_temp_rules_dir()
        with open(os.path.join(self.temp_rules_dir, 'test_1.ini'), 'a') as fp:
            fp.write("""
[rule]
enabled = yes
name = unit_test_1
description = Unit Test Description 1
type = test
alert_type = test - alert
frequency = */1 * * *
tags = tag1, tag2""")

        hunter = HuntManager(**self.manager_kwargs())
        hunter.load_hunts_from_config()
        self.assertEquals(len(hunter.hunts), 0)
        self.assertEquals(len(hunter.failed_ini_files), 1)

    def test_hunt_suppression(self):
        self.clear_temp_rules_dir()
        with open(os.path.join(self.temp_rules_dir, 'test_1.ini'), 'a') as fp:
            fp.write("""
[rule]
enabled = yes
name = unit_test_1
description = Unit Test Description 1
type = test
alert_type = test - alert
frequency = 00:00:01
suppression = 00:01:00
tags = tag1, tag2""")

        hunter = HuntManager(**self.manager_kwargs())
        hunter.load_hunts_from_config()
        self.assertEquals(len(hunter.hunts), 1)
        self.assertTrue(isinstance(hunter.hunts[0], TestHunt))
        self.assertIsNotNone(hunter.hunts[0].suppression)

        hunter.execute()
        hunter.manager_control_event.set()
        hunter.wait_control_event.set()
        hunter.wait()
        self.assertTrue(hunter.hunts[0].executed)
        # should have set suppression
        self.assertIsNotNone(hunter.hunts[0].suppression_end)

        # clear the flags that say this executed
        hunter.hunts[0].executed = False
        hunter.hunts[0]._last_executed_time = None
        hunter.manager_control_event.clear()
        hunter.wait_control_event.clear()
        hunter.execute()
        hunter.manager_control_event.set()
        hunter.wait_control_event.set()
        hunter.wait()
        # it should not have executed again because it is suppressed
        self.assertFalse(hunter.hunts[0].executed)

        # set the suppression end time to now and clear the flags again
        hunter.hunts[0].suppression_end = datetime.datetime.now()
        hunter.hunts[0]._last_executed_time = None
        hunter.manager_control_event.clear()
        hunter.wait_control_event.clear()
        hunter.execute()
        hunter.manager_control_event.set()
        hunter.wait_control_event.set()
        hunter.wait()
        # now it should have executed again, and be suppressed again
        self.assertTrue(hunter.hunts[0].executed)
        self.assertIsNotNone(hunter.hunts[0].suppression_end)
