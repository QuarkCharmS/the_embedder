"""
Git utilities for smart repository cloning with automatic authentication detection.

This module handles:
- Auto-detection of SSH keys from standard locations
- Automatic fallback from no-auth to authenticated cloning
- Container-friendly SSH key mounting
- Clear error messages when credentials are needed
"""

import subprocess
import os
from pathlib import Path
from typing import Optional, Tuple
from app.logger import get_logger

logger = get_logger(__name__)


class GitCloneError(Exception):
    """Raised when git clone fails with helpful error message."""
    pass


def _is_ssh_url(git_url: str) -> bool:
    """
    Detect if URL is SSH format.

    Args:
        git_url: Git URL to check

    Returns:
        True if SSH format, False if HTTPS

    Examples:
        git@github.com:user/repo.git → True
        ssh://git@github.com/user/repo.git → True
        https://github.com/user/repo.git → False
    """
    return git_url.startswith('git@') or git_url.startswith('ssh://')


def _find_ssh_keys() -> list:
    """
    Find SSH keys in standard locations.

    Searches for:
    - ~/.ssh/id_rsa
    - ~/.ssh/id_ed25519
    - ~/.ssh/id_ecdsa
    - /root/.ssh/id_rsa (for containers running as root)
    - /root/.ssh/id_ed25519

    Returns:
        List of paths to found SSH private keys
    """
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
                # Check it's readable and looks like a private key
                try:
                    with open(key_path, 'r') as f:
                        content = f.read(100)
                        if 'PRIVATE KEY' in content:
                            found_keys.append(str(key_path))
                except (PermissionError, IOError):
                    continue
        except (PermissionError, OSError):
            continue

    return found_keys


def _clone_with_ssh(git_url: str, destination: Path) -> Tuple[bool, str]:
    """
    Clone repository using SSH with automatic key detection.

    Args:
        git_url: SSH-format git URL
        destination: Where to clone to

    Returns:
        Tuple of (success: bool, error_message: str)
    """
    # Auto-detect SSH keys from standard locations
    ssh_keys = _find_ssh_keys()

    # Try without specific key first (uses system SSH config)
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
        # If no SSH keys found, explain
        if not ssh_keys:
            return False, (
                f"SSH authentication failed. No SSH keys found.\n"
                f"For containers: Mount your SSH key to ~/.ssh/id_rsa or ~/.ssh/id_ed25519\n"
                f"For local: Run 'ssh-keygen -t ed25519' to generate a key\n"
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
            logger.info(f"Used SSH key: {key_path}")
            return True, ""
        except subprocess.CalledProcessError:
            continue

    # All SSH keys failed
    return False, (
        f"SSH authentication failed with all found keys: {', '.join(ssh_keys)}\n"
        f"Ensure your public key is added to the git provider.\n"
        f"Test with: ssh -T git@github.com"
    )


def _clone_with_https(git_url: str, destination: Path, git_token: Optional[str] = None) -> Tuple[bool, str]:
    """
    Clone repository using HTTPS.

    Tries in order:
    1. No authentication (public repo)
    2. With provided token (private repo)

    Args:
        git_url: HTTPS git URL
        destination: Where to clone to
        git_token: Optional access token

    Returns:
        Tuple of (success: bool, error_message: str)
    """
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
        # If no token provided, give helpful message
        if not git_token:
            if "Authentication failed" in e.stderr or "could not read Username" in e.stderr:
                return False, (
                    f"Repository appears to be private but no token provided.\n"
                    f"Generate a Personal Access Token:\n"
                    f"  GitHub: https://github.com/settings/tokens\n"
                    f"  GitLab: https://gitlab.com/-/profile/personal_access_tokens\n"
                    f"Then pass it as: git_token='your_token'\n"
                    f"Error: {e.stderr}"
                )
            else:
                # Some other error
                return False, f"Clone failed: {e.stderr}"

    # Try with token
    if git_token:
        # Inject token into URL
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
                f"Authentication with token failed.\n"
                f"Check that:\n"
                f"  1. Token is valid and not expired\n"
                f"  2. Token has 'repo' scope (for GitHub)\n"
                f"  3. You have access to this repository\n"
                f"Error: {e.stderr}"
            )

    return False, "Clone failed and no token provided"


def smart_git_clone(git_url: str, destination: Path, git_token: Optional[str] = None) -> None:
    """
    Smart git clone with automatic authentication detection and fallback.

    Strategy:
    1. Detect URL type (SSH vs HTTPS)
    2. For SSH:
       - Auto-detect SSH keys from standard locations (~/.ssh/id_rsa, id_ed25519, etc.)
       - Try system SSH config first
       - Fall back to each found key
    3. For HTTPS:
       - Try without auth first (public repo)
       - If fails and token provided, use token
       - If fails and no token, provide helpful error

    Container-friendly:
    - Automatically finds SSH keys mounted at standard locations
    - Works with both user and root home directories (~/.ssh/ and /root/.ssh/)

    Args:
        git_url: Git repository URL (SSH or HTTPS format)
        destination: Path where to clone the repository
        git_token: Optional personal access token (for HTTPS private repos)

    Raises:
        GitCloneError: If clone fails with detailed error message

    Examples:
        # Public repo (auto-detects, no auth needed)
        smart_git_clone("https://github.com/user/public-repo.git", Path("/tmp/repo"))

        # Private HTTPS repo with token
        smart_git_clone(
            "https://github.com/user/private-repo.git",
            Path("/tmp/repo"),
            git_token="ghp_token123"
        )

        # SSH repo (auto-detects SSH key from ~/.ssh/)
        smart_git_clone("git@github.com:user/repo.git", Path("/tmp/repo"))
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
    """
    Extract repository name from git URL.

    Args:
        git_url: Git URL (SSH or HTTPS)

    Returns:
        Repository name (without .git extension)

    Examples:
        https://github.com/user/my-repo.git → my-repo
        git@github.com:user/my-repo.git → my-repo
    """
    # Handle SSH format: git@github.com:user/repo.git
    if ':' in git_url and '@' in git_url:
        repo_name = git_url.split(':')[-1]
    else:
        # Handle HTTPS format: https://github.com/user/repo.git
        repo_name = git_url.rstrip('/').split('/')[-1]

    # Remove .git extension
    return repo_name.replace('.git', '')
