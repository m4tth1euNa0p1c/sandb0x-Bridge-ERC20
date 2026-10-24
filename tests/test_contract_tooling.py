"""Frontières d'écriture et utilisateurs des compilations de contrats."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('contract_verifier', Path(__file__).resolve().parents[1] / 'contracts/tools/verify.py')
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class ContractBuildPermissionsTests(unittest.TestCase):
    def test_non_root_linux_owner_is_preserved_in_container(self):
        with patch.object(verifier.os, 'name', 'posix'), patch.object(verifier.os, 'getuid', return_value=1001, create=True), patch.object(verifier.os, 'getgid', return_value=1002, create=True):
            self.assertEqual(verifier.container_user(), '1001:1002')

    def test_root_or_windows_orchestrator_does_not_make_compiler_root(self):
        with patch.object(verifier.os, 'name', 'posix'), patch.object(verifier.os, 'getuid', return_value=0, create=True):
            self.assertEqual(verifier.container_user(), '1000:1000')
        with patch.object(verifier.os, 'name', 'nt'):
            self.assertEqual(verifier.container_user(), '1000:1000')

    def test_sources_are_readonly_and_only_artifacts_are_writable(self):
        with tempfile.TemporaryDirectory(prefix='t3l4n-forge-policy-') as directory:
            root = Path(directory)
            with patch.object(verifier, 'ROOT', root), patch.object(verifier, 'execute', return_value={'exit_code': 0}) as execute:
                verifier.docker_forge(['build'])
            command = execute.call_args.args[0]
            mounts = [command[i + 1] for i, arg in enumerate(command) if arg == '-v']
            self.assertEqual(set(mounts), {str(root) + ':/work:ro', str(root/'out') + ':/work/out', str(root/'cache') + ':/work/cache'})
            self.assertIn('--read-only', command)
            self.assertEqual(command[command.index('--network') + 1], 'none')
            self.assertNotEqual(command[command.index('--user') + 1].split(':')[0], '0')


if __name__ == '__main__':
    unittest.main()
