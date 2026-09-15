"""Opt-in, bounded Railway browser diagnostics. Never reads or prints secrets."""
import os
from pathlib import Path
import signal
import subprocess
import sys
from urllib.request import urlopen


def resources():
    for name in ('memory.current', 'memory.max', 'memory.events', 'cpu.max', 'cpu.stat'):
        path = Path('/sys/fs/cgroup') / name
        if path.is_file():
            print(f'DIAG {name}: {path.read_text().strip().replace(chr(10), "; ")}', flush=True)


def browser_probe(mode):
    from utils.scraper import get_driver, load_timetable_page
    print(f'DIAG {mode}: starting ChromeDriver', flush=True)
    driver = get_driver()
    try:
        print(f'DIAG {mode}: browser created', flush=True)
        if mode == 'blank':
            driver.get('about:blank')
            print('DIAG blank: navigation returned', flush=True)
            assert driver.execute_script('return 2 + 2') == 4
            print('DIAG blank: renderer OK', flush=True)
        else:
            from data.edupage_catalog import TIMETABLE_NUM
            from bs4 import BeautifulSoup
            html = load_timetable_page(driver, f'https://tsue.edupage.org/timetable/view.php?num={TIMETABLE_NUM}&class=*281')
            svg = BeautifulSoup(html, 'html.parser').find('svg')
            assert svg is not None
            print(f'DIAG edupage: SVG OK, rectangles={len(svg.find_all("rect"))}', flush=True)
    finally:
        print(f'DIAG {mode}: closing browser', flush=True)
        driver.quit()


def run_probe(mode):
    # A stuck driver must not block startup indefinitely. Kill only this probe's
    # process group, including the Chrome processes it created, on Linux.
    child = subprocess.Popen([sys.executable, '-u', __file__, '--probe', mode],
                             start_new_session=(os.name == 'posix'))
    try:
        code = child.wait(timeout=90)
        print(f'DIAG {mode}: exit={code}', flush=True)
    except subprocess.TimeoutExpired:
        print(f'DIAG {mode}: HARD TIMEOUT after 90 seconds', flush=True)
        if os.name == 'posix':
            os.killpg(child.pid, signal.SIGKILL)
        else:
            child.kill()
        child.wait()


def main():
    print('DIAG BEGIN: browser and network only; no Sheets writes', flush=True)
    resources()
    for variable in ('CHROME_BIN', 'CHROMEDRIVER_PATH'):
        executable = os.getenv(variable)
        if executable:
            result = subprocess.run([executable, '--version'], capture_output=True,
                                    text=True, timeout=10)
            print(f'DIAG {variable}: {result.stdout.strip()}', flush=True)
    try:
        with urlopen('https://tsue.edupage.org/timetable/', timeout=20) as response:
            print(f'DIAG HTTPS: status={response.status}, bytes={len(response.read(1000000))}', flush=True)
    except Exception as exc:
        print(f'DIAG HTTPS: {type(exc).__name__}: {exc}', flush=True)
    for mode in ('blank', 'edupage'):
        run_probe(mode)
        resources()
    print('DIAG END', flush=True)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--probe':
        browser_probe(sys.argv[2])
    else:
        main()
