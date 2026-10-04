from pathlib import Path
import tempfile
import unittest
from engine import Store, Countdown


class FocusTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/"mola.db"
        self.store=Store(self.path)

    def test_tasks_survive_reopen(self):
        identifier=self.store.add(" Kitap oku ")
        self.store.toggle(identifier)
        reopened=Store(self.path)
        self.assertEqual(reopened.tasks()[0]["title"],"Kitap oku")
        self.assertEqual(reopened.tasks()[0]["done"],1)
        reopened.remove(identifier)
        self.assertEqual(reopened.tasks(),[])

    def test_duplicate_completion_counts_once(self):
        for _ in range(2): self.store.complete("same",1500,day="2026-10-04")
        self.assertEqual(self.store.today("2026-10-04"),(1,1500))
        self.assertEqual(self.store.today("2026-10-05"),(0,0))

    def test_backup_reopens_and_no_overwrite(self):
        self.store.add("Yedekle")
        target=Path(self.temp.name)/"backup.db"
        self.store.backup(target)
        self.assertEqual(Store(target).tasks()[0]["title"],"Yedekle")
        with self.assertRaises(FileExistsError): self.store.backup(target)

    def test_invalid_task(self):
        for title in (" ","x"*201):
            with self.assertRaises(ValueError): self.store.add(title)

    def test_pause_resume_uses_deadline(self):
        now=[10.0]
        timer=Countdown(60,clock=lambda:now[0])
        timer.start()
        now[0]+=20
        timer.pause()
        self.assertEqual(timer.remaining,40)
        now[0]+=500
        self.assertEqual(timer.tick(),40)
        timer.start()
        now[0]+=41
        self.assertEqual(timer.tick(),0)
        self.assertFalse(timer.running)

    def test_reset_gets_new_session_identity(self):
        timer=Countdown()
        identifier=timer.identifier
        timer.start()
        timer.reset(300)
        self.assertNotEqual(timer.identifier,identifier)
        self.assertEqual(timer.remaining,300)
        self.assertFalse(timer.running)


if __name__=="__main__": unittest.main()
