import os
import subprocess
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = {"approval-window": REPO, "approval-demo": os.path.join(REPO, "approval-demo")}


def run_install(home):
    env = {**os.environ, "HOME": home}
    return subprocess.run(["bash", os.path.join(REPO, "install.sh")], env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)


class InstallTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = os.path.realpath(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_links_cli_and_skills(self):
        r = run_install(self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        cli = os.path.join(self.home, ".local/bin/awin")
        self.assertTrue(os.path.islink(cli))
        self.assertEqual(os.path.realpath(cli), os.path.join(REPO, "awin.py"))
        for name, target in SKILLS.items():
            agents = os.path.join(self.home, ".agents/skills", name)
            self.assertTrue(os.path.islink(agents))
            self.assertEqual(os.readlink(agents), target)
            for host in (".claude", ".cursor", ".codex"):
                link = os.path.join(self.home, host, "skills", name)
                self.assertTrue(os.path.islink(link), link)
                self.assertEqual(os.readlink(link), "../../.agents/skills/" + name)

    def test_awin_is_executable(self):
        run_install(self.home)
        self.assertTrue(os.access(os.path.join(REPO, "awin.py"), os.X_OK))

    def test_rerun_is_safe(self):
        self.assertEqual(run_install(self.home).returncode, 0)
        r = run_install(self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(os.readlink(os.path.join(self.home, ".local/bin/awin")),
                         os.path.join(REPO, "awin.py"))

    def test_real_file_is_never_replaced(self):
        path = os.path.join(self.home, ".local/bin/awin")
        os.makedirs(os.path.dirname(path))
        with open(path, "w") as f:
            f.write("mine")
        r = run_install(self.home)
        self.assertEqual(r.returncode, 1)
        self.assertIn("refusing to replace", r.stderr)
        with open(path) as f:
            self.assertEqual(f.read(), "mine")

    def test_real_dir_in_skills_is_never_replaced(self):
        path = os.path.join(self.home, ".claude/skills/approval-window")
        os.makedirs(path)
        r = run_install(self.home)
        self.assertEqual(r.returncode, 1)
        self.assertFalse(os.path.islink(path))

    def test_other_skills_are_untouched(self):
        other = os.path.join(self.home, ".agents/skills/other")
        os.makedirs(other)
        run_install(self.home)
        self.assertTrue(os.path.isdir(other))


if __name__ == "__main__":
    unittest.main()
