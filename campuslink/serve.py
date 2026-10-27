"""Single-process hosted launcher; secrets stay in environment variables."""
import os
from pathlib import Path
import sys

from .deployment import Deployment


def options():
    deployment = Deployment.load(Path(__file__).resolve().parent.parent)
    if deployment.mode != 'staging':
        raise RuntimeError('The hosted launcher requires CAMPUSLINK_MODE=staging.')
    try:
        port = int(os.getenv('PORT', '8001'))
        if not 1 <= port <= 65535:
            raise ValueError()
    except ValueError:
        raise RuntimeError('PORT must be an integer between 1 and 65535.') from None
    proxies = os.getenv('CAMPUSLINK_TRUSTED_PROXY_IPS') or ('*' if os.getenv('RENDER') == 'true' else '127.0.0.1')
    return deployment, {'host': '0.0.0.0', 'port': port, 'workers': 1, 'proxy_headers': True,
                        'forwarded_allow_ips': proxies, 'timeout_graceful_shutdown': 3}


def main():
    deployment, config = options()
    if sys.argv[1:] == ['--check']:
        print(f'Valid hosted preview configuration: {deployment.origin}; database={deployment.database}; workers=1')
        return
    if sys.argv[1:]:
        raise SystemExit('Usage: python -m campuslink.serve [--check]')
    import uvicorn
    uvicorn.run('campuslink.app:app', **config)


if __name__ == '__main__':
    main()
