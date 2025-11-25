"""
Smart git cloning with automatic authentication detection.

Functions:
- smart_git_clone(): Clone repo with SSH/HTTPS auto-detection and auth fallback
- get_repo_name_from_url(): Extract repository name from git URL

See ARCHITECTURE.md for detailed flow and logic.
"""

import subprocess
import os
from pathlib import Path
from typing import Optional, Tuple
from app.logger import get_logger

logger = get_logger(__name__)


class GitCloneError(Exception):
    """Raised when git clone fails with helpful error message."""


def _is_ssh_url(git_url: str) -> bool:
    """Detect if URL is SSH format (git@ or ssh://)."""
    return git_url.startswith('git@') or git_url.startswith('ssh://')


def _find_ssh_keys() -> list:
    """Find SSH private keys in standard locations."""
    potential_keys = [
        Path.home() / '.ssh' / 'id_rsa',
        Path.home() / '.ssh' / 'id_ed25519',
        Path.home() / '.ssh' / 'id_ecdsa',
        Path('/root/.ssh/id_rsa'),
        Path('/root/.ssh/id_ed25519'),
    ]

    found_keys = []
    for key_path in potential_keys:
        try:
            if key_path.exists() and key_path.is_file():
                try:
                    with open(key_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read(100)
                        if 'PRIVATE KEY' in content:
                            found_keys.append(str(key_path))
                except (PermissionError, IOError):
                    continue
        except (PermissionError, OSError):
            continue

    return found_keys


def _clone_with_ssh(git_url: str, destination: Path) -> Tuple[bool, str]:
    """Clone repository using SSH with automatic key detection."""
    ssh_keys = _find_ssh_keys()

    # Try without specific key first (uses system SSH config)
    try:
        subprocess.run(
            ["git", "clone", "--depth=1", git_url, str(destination)],
            check=True,
            capture_output=True,
            text=True,
            timeout=300
        )
        return True, ""
    except subprocess.CalledProcessError as e:
        if not ssh_keys:
            return False, (
                "SSH authentication failed. No SSH keys found.\n"
                "For containers: Mount your SSH key to ~/.ssh/id_rsa or ~/.ssh/id_ed25519\n"
                "For local: Run 'ssh-keygen -t ed25519' to generate a key\n"
                f"Error: {e.stderr}"
            )

    # Try with each found SSH key
    for key_path in ssh_keys:
        try:
            git_env = os.environ.copy()
            git_env['GIT_SSH_COMMAND'] = f'ssh -i {key_path} -o StrictHostKeyChecking=no'

            subprocess.run(
                ["git", "clone", git_url, str(destination)],
                check=True,
                capture_output=True,
                text=True,
                env=git_env,
                timeout=300
            )
            logger.info("Used SSH key: %s", key_path)
            return True, ""
        except subprocess.CalledProcessError:
            continue

    # All SSH keys failed
    return False, (
        f"SSH authentication failed with all found keys: {', '.join(ssh_keys)}\n"
        "Ensure your public key is added to the git provider.\n"
        "Test with: ssh -T git@github.com"
    )


def _clone_with_https(git_url: str, destination: Path, git_token: Optional[str] = None) -> Tuple[bool, str]:
    """Clone repository using HTTPS with optional token authentication."""
    # Try without authentication first (public repo)
    try:
        subprocess.run(
            ["git", "clone", git_url, str(destination)],
            check=True,
            capture_output=True,
            text=True,
            timeout=300
        )
        return True, ""
    except subprocess.CalledProcessError as e:
        if not git_token:
            if "Authentication failed" in e.stderr or "could not read Username" in e.stderr:
                return False, (
                    "Repository appears to be private but no token provided.\n"
                    "Generate a Personal Access Token:\n"
                    "  GitHub: https://github.com/settings/tokens\n"
                    "  GitLab: https://gitlab.com/-/profile/personal_access_tokens\n"
                    "Then pass it as: git_token='your_token'\n"
                    f"Error: {e.stderr}"
                )
            return False, f"Clone failed: {e.stderr}"

    # Try with token
    if git_token:
        auth_url = git_url.replace('https://', f'https://{git_token}@')

        try:
            subprocess.run(
                ["git", "clone", auth_url, str(destination)],
                check=True,
                capture_output=True,
                text=True,
                timeout=300
            )
            logger.info("Authenticated with provided token")
            return True, ""
        except subprocess.CalledProcessError as e:
            return False, (
                "Authentication with token failed.\n"
                "Check that:\n"
                "  1. Token is valid and not expired\n"
                "  2. Token has 'repo' scope (for GitHub)\n"
                "  3. You have access to this repository\n"
                f"Error: {e.stderr}"
            )

    return False, "Clone failed and no token provided"


def smart_git_clone(git_url: str, destination: Path, git_token: Optional[str] = None) -> None:
    """
    Smart git clone with automatic authentication detection and fallback.

    Auto-detects URL type, finds SSH keys, and provides helpful errors.
    """
    is_ssh = _is_ssh_url(git_url)

    if is_ssh:
        logger.info("Detected SSH URL")
        success, error = _clone_with_ssh(git_url, destination)
    else:
        logger.info("Detected HTTPS URL")
        success, error = _clone_with_https(git_url, destination, git_token)

    if not success:
        raise GitCloneError(error)


def get_repo_name_from_url(git_url: str) -> str:
    """Extract repository name from git URL."""
    # Handle SSH format: git@github.com:user/repo.git
    if ':' in git_url and '@' in git_url:
        repo_name = git_url.split(':')[-1]
    else:
        # Handle HTTPS format: https://github.com/user/repo.git
        repo_name = git_url.rstrip('/').split('/')[-1]

    return repo_name.replace('.git', '')
