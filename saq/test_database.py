# vim: sw=4:ts=4:et

import logging
import multiprocessing
import threading
import time
import unittest
import uuid

from multiprocessing import Process, Event, Pipe

import saq
import saq.database
import saq.test

from saq.constants import *
from saq.database import (
        get_db_connection, 
        get_pool,
        Alert, 
        use_db,
        acquire_lock, 
        release_lock,
        execute_with_retry )

from saq.test import *

import pymysql.err

class TestCase(ACEBasicTestCase):

    def test_session(self):
        from sqlalchemy.orm.session import Session
        self.assertTrue(isinstance(saq.db(), Session))

    @use_db
    def test_execute_with_retry(self, db, c):
        # simple single statement transaction
        execute_with_retry(db, c, [ 'SELECT 1' ], [ tuple() ])
        db.commit()

        # multi statement transaction
        _uuid = str(uuid.uuid4())
        _lock_uuid = str(uuid.uuid4())
        execute_with_retry(db, c, [ 
            'INSERT INTO locks ( uuid, lock_time ) VALUES ( %s, NOW() )',
            'UPDATE locks SET lock_uuid = %s WHERE uuid = %s',
            'DELETE FROM locks WHERE uuid = %s',
        ], [ 
            (_uuid,),
            (_lock_uuid, _uuid),
            (_uuid,),
        ])
        db.commit()

    def test_execute_with_retry_commit(self):
        _uuid = str(uuid.uuid4())
        _lock_uuid = str(uuid.uuid4())

        # simple insert statement with commit option
        with get_db_connection() as db:
            c = db.cursor()
            execute_with_retry(db, c, 'INSERT INTO locks ( uuid, lock_time ) VALUES ( %s, NOW() )', (_uuid,), commit=True)

        # check it on another connection
        with get_db_connection() as db:
            c = db.cursor()
            c.execute("SELECT uuid FROM locks WHERE uuid = %s", (_uuid,))
            self.assertIsNotNone(c.fetchone())

        _uuid = str(uuid.uuid4())
        _lock_uuid = str(uuid.uuid4())

        # and then this one should fail since we did not commit it
        with get_db_connection() as db:
            c = db.cursor()
            execute_with_retry(db, c, 'INSERT INTO locks ( uuid, lock_time ) VALUES ( %s, NOW() )', (_uuid,), commit=False)

        with get_db_connection() as db:
            c = db.cursor()
            c.execute("SELECT uuid FROM locks WHERE uuid = %s", (_uuid,))
            self.assertIsNone(c.fetchone())

    @unittest.skip
    def test_deadlock(self):
        # make sure we can always generate a deadlock
        _uuid = str(uuid.uuid4())
        _lock_uuid = str(uuid.uuid4())

        with get_db_connection() as db:
            c = db.cursor()
            c.execute("INSERT INTO locks ( uuid, lock_uuid, lock_time ) VALUES ( %s, %s, NOW() )", ( _uuid, _lock_uuid ))
            db.commit()

        # one of these threads will get a deadlock
        def _t1():
            _uuid = str(uuid.uuid4())
            _lock_uuid = str(uuid.uuid4())
            try:
                with get_db_connection() as db:
                    c = db.cursor()
                    c.execute("INSERT INTO locks ( uuid, lock_time ) VALUES ( %s, NOW() )", (_uuid,))
                    # wait for signal to continue
                    time.sleep(2)
                    c.execute("UPDATE locks SET lock_owner = 'whatever'")
                    db.commit()
            except pymysql.err.OperationalError as e:
                if e.args[0] == 1213 or e.args[0] == 1205:
                    deadlock_event.set()

        def _t2():
            _uuid = str(uuid.uuid4())
            _lock_uuid = str(uuid.uuid4())
            try:
                with get_db_connection() as db:
                    c = db.cursor()
                    c.execute("UPDATE locks SET lock_owner = 'whatever'")
                    # wait for signal to continue
                    time.sleep(2)
                    c.execute("INSERT INTO locks ( uuid, lock_time ) VALUES ( %s, NOW() )", (_uuid,))
                    db.commit()
            except pymysql.err.OperationalError as e:
                if e.args[0] == 1213 or e.args[0] == 1205:
                    deadlock_event.set()

        deadlock_event = threading.Event()

        t1 = threading.Thread(target=_t1)
        t2 = threading.Thread(target=_t2)

        t1.start()
        t2.start()

        self.assertTrue(deadlock_event.wait(5))
        t1.join(5)
        t2.join(5)

        self.assertFalse(t1.is_alive())
        self.assertFalse(t2.is_alive())

    @unittest.skip
    def test_retry_on_deadlock(self):
        # make sure our code to retry failed transactions on deadlocks
        _uuid = str(uuid.uuid4())
        _lock_uuid = str(uuid.uuid4())

        with get_db_connection() as db:
            c = db.cursor()
            c.execute("INSERT INTO locks ( uuid, lock_uuid, lock_time ) VALUES ( %s, %s, NOW() )", ( _uuid, _lock_uuid ))
            db.commit()

        # one of these threads will get a deadlock
        def _t1():
            _uuid = str(uuid.uuid4())
            _lock_uuid = str(uuid.uuid4())
            try:
                with get_db_connection() as db:
                    c = db.cursor()
                    execute_with_retry(db, c, "INSERT INTO locks ( uuid, lock_time ) VALUES ( %s, NOW() )", (_uuid,))
                    # wait for signal to continue
                    time.sleep(2)
                    execute_with_retry(db, c, "UPDATE locks SET lock_owner = 'whatever'")
                    db.commit()
            except pymysql.err.OperationalError as e:
                if e.args[0] == 1213 or e.args[0] == 1205:
                    deadlock_event.set()

        def _t2():
            _uuid = str(uuid.uuid4())
            _lock_uuid = str(uuid.uuid4())
            try:
                with get_db_connection() as db:
                    c = db.cursor()
                    execute_with_retry(db, c, "UPDATE locks SET lock_owner = 'whatever'")
                    # wait for signal to continue
                    time.sleep(2)
                    execute_with_retry(db, c, "INSERT INTO locks ( uuid, lock_time ) VALUES ( %s, NOW() )", (_uuid,))
                    db.commit()
            except pymysql.err.OperationalError as e:
                if e.args[0] == 1213 or e.args[0] == 1205:
                    deadlock_event.set()

        deadlock_event = threading.Event()

        t1 = threading.Thread(target=_t1)
        t2 = threading.Thread(target=_t2)

        t1.start()
        t2.start()

        self.assertFalse(deadlock_event.wait(5))
        t1.join(5)
        t2.join(5)

        self.assertFalse(t1.is_alive())
        self.assertFalse(t2.is_alive())

        self.assertEquals(log_count('deadlock detected'), 1)

    def insert_alert(self):
        root = create_root_analysis(uuid=str(uuid.uuid4()))
        root.initialize_storage()
        root.save()

        alert = Alert(storage_dir=root.storage_dir)
        alert.load()
        alert.sync()
        self.assertIsNotNone(alert.id)
        return alert

    def test_load_alert(self):
        # since we're storing the data in two places (json and database)
        # make sure that when we load() and Alert we don't immediately make it "dirty" to the ORM

        alert = self.insert_alert()
        alert_id = alert.id
        saq.db.close()
        self.assertFalse(saq.db.dirty)

        for alert in saq.db.query(Alert).filter(Alert.id == alert_id):
            self.assertFalse(saq.db.dirty)
            alert.load()
            self.assertFalse(saq.db.dirty)

    def test_connection(self):
        with get_db_connection() as db:
            c = db.cursor()
            c.execute("SELECT 1")

        session = saq.database.DatabaseSession()
        self.assertIsNotNone(session)

    def test_insert_alert(self):
        alert = self.insert_alert()

    def test_lock(self):
        alert = self.insert_alert()

        lock_uuid = acquire_lock(alert.uuid)
        self.assertTrue(lock_uuid)
        # something that was locked is locked
        self.assertTrue(alert.is_locked())
        # and can be locked again
        self.assertEquals(lock_uuid, acquire_lock(alert.uuid, lock_uuid))
        # can be unlocked
        self.assertTrue(release_lock(alert.uuid, lock_uuid))
        # truely is unlocked
        self.assertFalse(alert.is_locked())
        # cannot be unlocked again  
        self.assertFalse(release_lock(alert.uuid, lock_uuid))
        # and can be locked again
        self.assertTrue(acquire_lock(alert.uuid))
        self.assertTrue(alert.is_locked())

    #@unittest.skip("...")
    def test_multiprocess_lock(self):
        alert = self.insert_alert()
        sync0 = Event()
        sync1 = Event()
        sync2 = Event()

        def p1(alert_id):
            session = saq.database.DatabaseSession()
            alert = session.query(Alert).filter(Alert.id == alert_id).one()
            lock_uuid = acquire_lock(alert.uuid)
            # tell parent to get the lock
            sync0.set()
            # wait for parent to signal
            sync1.wait()
            release_lock(alert.uuid, lock_uuid)
            sync2.set()

        p = Process(target=p1, args=(alert.id,))
        p.start()

        try:
            sync0.wait()
            
            # lock should already be locked
            self.assertTrue(alert.is_locked())
            # should not be able to lock the lock
            self.assertFalse(acquire_lock(alert.uuid))

            sync1.set()
            sync2.wait()
            # lock should be unlocked
            self.assertFalse(alert.is_locked())
            # and we should be able to lock it
            lock_uuid = acquire_lock(alert.uuid)
            self.assertTrue(uuid)
            self.assertTrue(alert.is_locked())
            self.assertTrue(release_lock(alert.uuid, lock_uuid))
            self.assertFalse(alert.is_locked())
            
            p.join()
            p = None
        finally:
            if p:
                p.terminate()
                p.join()

    def test_expired(self):
        # set locks to expire immediately
        saq.LOCK_TIMEOUT_SECONDS = 0
        alert = self.insert_alert()
        lock_uuid = acquire_lock(alert.uuid)
        self.assertTrue(lock_uuid)
        # should expire right away
        self.assertFalse(alert.is_locked())
        # and we are able to lock it again
        lock_uuid = acquire_lock(alert.uuid)
        self.assertTrue(lock_uuid)

    def test_pooling(self):
        get_pool().clear()
        with get_db_connection() as db_1:
            # we should have one database connection ready
            self.assertEquals(get_pool().in_use_count, 1)
            self.assertEquals(get_pool().available_count, 0)
            with get_db_connection() as db_2:
                self.assertEquals(get_pool().in_use_count, 2)
                self.assertEquals(get_pool().available_count, 0)
                self.assertFalse(db_1 is db_2)

            self.assertEquals(get_pool().in_use_count, 1)
            self.assertEquals(get_pool().available_count, 1)

        self.assertEquals(get_pool().in_use_count, 0)
        self.assertEquals(get_pool().available_count, 2)

    def test_pooling_old_connection(self):
        get_pool().clear()
        # made them invalid immediately
        saq.CONFIG['database']['max_connection_lifetime'] = '00:00:00'

        with get_db_connection() as _:
            pass

        self.assertEquals(log_count('got new database connection to'), 1)

        with get_db_connection() as _:
            pass

        self.assertEquals(log_count('got new database connection to'), 2)

        # change it back and then we should start re-using the connections again
        get_pool().clear()
        saq.CONFIG['database']['max_connection_lifetime'] = '00:01:00'

        with get_db_connection() as _:
            pass

        self.assertEquals(log_count('got new database connection to'), 3)

        with get_db_connection() as _:
            pass

        self.assertEquals(log_count('got new database connection to'), 3)

    def test_pooling_without_contextmanager(self):
        get_pool().clear()
        db = get_pool().get_connection()

        self.assertEquals(get_pool().in_use_count, 1)
        self.assertEquals(get_pool().available_count, 0)

        c = db.cursor()
        c.execute("SELECT 1")
        db.commit()
        get_pool().return_connection(db)

        self.assertEquals(get_pool().in_use_count, 0)
        self.assertEquals(get_pool().available_count, 1)

    def test_pooling_bad_sql(self):
        get_pool().clear()
        with get_db_connection() as db_1:

            self.assertEquals(get_pool().in_use_count, 1)
            self.assertEquals(get_pool().available_count, 0)

            with self.assertRaises(Exception):
                c = db_1.cursor()
                c.execute("INVALID SQL")

        self.assertEquals(get_pool().in_use_count, 0)
        self.assertEquals(get_pool().available_count, 1)

        with get_db_connection() as db_1:

            self.assertEquals(get_pool().in_use_count, 1)
            self.assertEquals(get_pool().available_count, 0)

            c = db_1.cursor()
            c.execute("SELECT 1")
            c.fetchone()
            db_1.commit()

        self.assertEquals(get_pool().in_use_count, 0)
        self.assertEquals(get_pool().available_count, 1)

    def test_pooling_broken_connection(self):
        get_pool().clear()
        with get_db_connection() as db_1:

            self.assertEquals(get_pool().in_use_count, 1)
            self.assertEquals(get_pool().available_count, 0)
            db_1.close()

        self.assertEquals(get_pool().in_use_count, 0)
        self.assertEquals(get_pool().available_count, 0)

        with get_db_connection() as db_1:

            self.assertEquals(get_pool().in_use_count, 1)
            self.assertEquals(get_pool().available_count, 0)

            c = db_1.cursor()
            c.execute("SELECT 1")
            c.fetchone()
            db_1.commit()

        self.assertEquals(get_pool().in_use_count, 0)
        self.assertEquals(get_pool().available_count, 1)

    def test_pooling_threaded(self):
        get_pool().clear()

        with get_db_connection() as conn_1:
            self.assertEquals(get_pool().in_use_count, 1)
            self.assertEquals(get_pool().available_count, 0)

            def f():
                with get_db_connection() as conn_2:
                    self.assertFalse(conn_1 is conn_2)
                    self.assertEquals(get_pool().in_use_count, 2)
                    self.assertEquals(get_pool().available_count, 0)

                # but asked a second time this should be the same as before
                with get_db_connection() as conn_3:
                    self.assertTrue(conn_3 is conn_2)
                    self.assertEquals(get_pool().in_use_count, 2)
                    self.assertEquals(get_pool().available_count, 0)
                
            self.assertEquals(get_pool().in_use_count, 1)
            self.assertEquals(get_pool().available_count, 0)
            t = threading.Thread(target=f)
            t.start()
            t.join()
                    
        self.assertEquals(get_pool().in_use_count, 0)
        self.assertEquals(get_pool().available_count, 2)

        # make sure we can get, and use, the connection created in the other thread

        conn_1 = get_pool().get_connection()
        conn_2 = get_pool().get_connection()

        self.assertEquals(get_pool().in_use_count, 2)
        self.assertEquals(get_pool().available_count, 0)

        c = conn_2.cursor()
        c.execute("SELECT 1")
        c.fetchone()

        get_pool().return_connection(conn_1)
        get_pool().return_connection(conn_2)

        self.assertEquals(get_pool().in_use_count, 0)
        self.assertEquals(get_pool().available_count, 2)

    def test_pooling_multi_process(self):
        get_pool().clear()
        with get_db_connection() as conn_1:
            self.assertEquals(get_pool().in_use_count, 1)
            self.assertEquals(get_pool().available_count, 0)

            def f():
                # once we've entered into the new process, the pool changes
                send_test_message(get_pool().in_use_count == 0)
                send_test_message(get_pool().available_count == 0)

                # so this connection should be different than conn_1
                with get_db_connection() as conn_2:
                    send_test_message(not (conn_1 is conn_2))
                    send_test_message(get_pool().in_use_count == 1)
                    send_test_message(get_pool().available_count == 0)

                send_test_message(get_pool().in_use_count == 0)
                send_test_message(get_pool().available_count == 1)

            p = multiprocessing.Process(target=f)
            p.start()

            self.assertTrue(recv_test_message()) 
            self.assertTrue(recv_test_message()) 
            self.assertTrue(recv_test_message()) 
            self.assertTrue(recv_test_message())

            p.join()

        self.assertEquals(get_pool().in_use_count, 0)
        self.assertEquals(get_pool().available_count, 1)

        with get_db_connection() as conn_4:
            self.assertEquals(get_pool().in_use_count, 1)
            self.assertEquals(get_pool().available_count, 0)
            self.assertTrue(conn_1 is conn_4)

    def test_insert_alert(self):
        #root_analysis = create_root_analysis()
        #root_analysis.save()
        #alert = Alert(storage_dir=root_analysis.storage_dir)
        #alert.load()
        #alert.sync()

        # make an alert with a description that is too long
        root_analysis = create_root_analysis(desc = 'A' * 1025)
        root_analysis.save()
        alert = Alert(storage_dir=root_analysis.storage_dir)
        alert.load()
        alert.sync()

        self.assertEquals(len(alert.description), 1024)

    def test_sync_observable_mapping(self):
        root_analysis = create_root_analysis()
        root_analysis.save()
        alert = Alert(storage_dir=root_analysis.storage_dir)
        alert.load()
        alert.sync()

        o1 = alert.add_observable(F_TEST, 'test_1')
        alert.sync_observable_mapping(o1)

        from saq.database import Observable, ObservableMapping
        from sqlalchemy import func
        observable = saq.db.query(Observable).filter(Observable.type == o1.type, Observable.md5 == func.UNHEX(o1.md5_hex)).first()
        self.assertIsNotNone(observable)

    # XXX fix this
    @unittest.skip("Now this one is failing too -- need to revisit this soon.")
    def test_retry_function_on_deadlock(self):

        from saq.database import User, retry_function_on_deadlock

        with get_db_connection() as db:
            c = db.cursor()
            c.execute("INSERT INTO users ( username, email ) VALUES ( 'user0', 'user0@localhost' )")
            c.execute("INSERT INTO users ( username, email ) VALUES ( 'user1', 'user1@localhost' )")
            db.commit()

        lock_user0 = threading.Event()
        lock_user1 = threading.Event()

        def _t1():
            # acquire lock on user0
            saq.db.execute(User.__table__.update().where(User.username == 'user0').values(email='user0@t1'))
            lock_user0.set()
            # wait for lock on user1
            lock_user1.wait(5)
            time.sleep(2)
            # this should fire a deadlock
            saq.db.execute(User.__table__.update().where(User.username == 'user1').values(email='user1@t1'))
            saq.db.commit()

        def _t2():
            with get_db_connection() as db:
                c = db.cursor()
                lock_user0.wait(5)
                # acquire lock on user1
                c.execute("UPDATE users SET email = 'user1@t2' WHERE username = 'user1'")
                lock_user1.set()
                # this will block waiting for lock on user0
                c.execute("UPDATE users SET email = 'user0@t2' WHERE username = 'user0'")
                db.commit()

        t1 = threading.Thread(target=retry_function_on_deadlock, args=(_t1,))
        t1.start()
        t2 = threading.Thread(target=_t2)
        t2.start()

        t1.join(5)
        t2.join(5)

        self.assertEquals(log_count('DEADLOCK STATEMENT'), 1)
        self.assertIsNotNone(saq.db.query(User).filter(User.email == 'user0@t1', 
                                                       User.username == 'user0').first())
        self.assertIsNotNone(saq.db.query(User).filter(User.email == 'user1@t1', 
                                                       User.username == 'user1').first())

    @unittest.skip("Can't seem to get this one to always fire.")
    def test_retry_sql_on_deadlock(self):

        from saq.database import User, retry_sql_on_deadlock

        with get_db_connection() as db:
            c = db.cursor()
            c.execute("INSERT INTO users ( username, email ) VALUES ( 'user0', 'user0@localhost' )")
            c.execute("INSERT INTO users ( username, email ) VALUES ( 'user1', 'user1@localhost' )")
            db.commit()

        lock_user0 = threading.Event()
        lock_user1 = threading.Event()

        def _t1():
            session = saq.db()
            # acquire lock on user0
            retry_sql_on_deadlock(User.__table__.update().where(User.username == 'user0')
                                                         .values(email='user0@_t1'),
                                  session=session)
            lock_user0.set()
            # wait for lock on user1
            lock_user1.wait(5)
            time.sleep(2)
            # this should fire a deadlock
            # 3/8/2019 - used to expect the deadlock here, but it can also happen in the first statement of _t2
            retry_sql_on_deadlock(User.__table__.update().where(User.username == 'user1')
                                                         .values(email='user1@_t1'),
                                  session=session,
                                  commit=True) 
        def _t2():
            with get_db_connection() as db:
                c = db.cursor()
                lock_user0.wait(5)
                # acquire lock on user1
                execute_with_retry(db, c, "UPDATE users SET email = 'user1@_t2' WHERE username = 'user1'")
                lock_user1.set()
                # this will block waiting for lock on user0
                execute_with_retry(db, c, "UPDATE users SET email = 'user0@_t2' WHERE username = 'user0'")
                db.commit()

        t1 = threading.Thread(target=_t1)
        t1.start()
        t2 = threading.Thread(target=_t2)
        t2.start()

        t1.join(5)
        t2.join(5)

        self.assertEquals(log_count('DEADLOCK STATEMENT'), 1)
        self.assertIsNotNone(saq.db.query(User).filter(User.email == 'user0@_t2', 
                                                       User.username == 'user0').first())
        self.assertIsNotNone(saq.db.query(User).filter(User.email == 'user1@_t1', 
                                                       User.username == 'user1').first())
