import concurrent.futures
import hashlib
import json
import os
import pathlib
import platform
import subprocess
import sys
import time
import urllib.request

root = pathlib.Path('platform-runtime').resolve()
root.mkdir(exist_ok=True)
base_env = dict(os.environ, MINECRAFT_EULA='true', PARKOURSE_PORT='25586',
                JAVA_TOOL_OPTIONS='-XX:ActiveProcessorCount=2')
jar = root / 'server.jar'

def get(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=25) as response:
                return response.read()
        except OSError:
            if attempt == 2:
                raise

def download(url, checksum, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and hashlib.sha1(path.read_bytes()).hexdigest() == checksum:
        return
    data = get(url)
    assert hashlib.sha1(data).hexdigest() == checksum, path
    path.write_bytes(data)

def download_entry(item):
    entry, path = item
    download(entry['url'], entry['sha1'], path)

def version():
    file = root / 'version.json'
    if not file.exists():
        manifest = json.loads(get('https://piston-meta.mojang.com/mc/game/version_manifest_v2.json'))
        entry = next(v for v in manifest['versions'] if v['id'] == '26.1.2')
        download(entry['url'], entry['sha1'], file)
    return json.loads(file.read_text())

def wait_for(file, predicate, process, timeout=100):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate(file.read_text(errors='replace')):
            return
        if process.poll() is not None:
            break
        time.sleep(0.3)
    print(file.read_text(errors='replace')[-5000:])
    raise RuntimeError(f'Expected Minecraft output was missing in {file.name}')

def start_server(run_dir, log, world=None):
    args = ['bash', './scripts/headless', jar.as_posix()]
    if world:
        args.append(world.as_posix())
    run_env = dict(base_env, PARKOURSE_RUN_DIR=run_dir.as_posix())
    with log.open('w') as output:
        return subprocess.Popen(args, env=run_env, stdin=subprocess.PIPE, stdout=output,
                                stderr=subprocess.STDOUT, text=True)

def send(server, command):
    server.stdin.write(command + '\n')
    server.stdin.flush()

def stop(server):
    if server.poll() is None:
        send(server, 'stop')
        try:
            server.wait(timeout=25)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()

def jump():
    lines = [
        '{"op":"reset","start":[0.5,-60,0.5],"yaw":0}',
        '{"op":"step","action":"run_jump"}',
        '{"op":"reset","start":[0.5,-60,0.5],"yaw":0}',
    ]
    bot = subprocess.run(['node', 'src/minecraft.ts'], env=base_env, text=True, check=True,
                         input='\n'.join(lines) + '\n', capture_output=True, timeout=30)
    replies = [json.loads(line)['result'] for line in bot.stdout.splitlines()]
    start, frames, end = replies
    assert start == end and start['on_ground'] and len(frames) == 2, replies
    assert not frames[-1]['on_ground'] and frames[-1]['position'][1] > start['position'][1], replies
    print(f'{platform.platform()}: server reset, two jump frames, reset restored.', flush=True)

def check_server():
    download_entry((version()['downloads']['server'], jar))
    first = root / 'source'
    log = root / 'generate.log'
    server = start_server(first, log)
    try:
        wait_for(log, lambda text: 'Done (' in text, server)
    finally:
        stop(server)
    source = first / 'world'
    before = hashlib.sha1((source / 'level.dat').read_bytes()).hexdigest()
    log = root / 'headless.log'
    server = start_server(root / 'run with spaces', log, source)
    try:
        wait_for(log, lambda text: 'Done (' in text, server)
        jump()
    finally:
        stop(server)
    assert before == hashlib.sha1((source / 'level.dat').read_bytes()).hexdigest()
    print('Loaded a real save into a separate folder. The source did not change.', flush=True)

def client_command():
    v = version()
    client = root / 'client.jar'
    assets = root / 'assets'
    index = assets / 'indexes' / (v['assetIndex']['id'] + '.json')
    targets = [(v['downloads']['client'], client), (v['assetIndex'], index)]
    classpath = [str(client)]
    os_name = {'darwin': 'osx', 'win32': 'windows'}[sys.platform]
    is_arm = platform.machine().lower() in ('aarch64', 'arm64')
    for lib in v['libraries']:
        rules = lib.get('rules', [])
        allowed = not rules
        for rule in rules:
            os_rule = rule.get('os', {})
            if os_rule.get('name', os_name) == os_name and not rule.get('features'):
                allowed = rule['action'] == 'allow'
        classifier = lib['name'].split(':')[-1]
        if classifier.startswith('natives-'):
            if classifier.endswith('-x86') or classifier.endswith('-arm64') != is_arm:
                allowed = False
            if not is_arm and classifier.endswith('-x64'):
                allowed = True
        if not allowed:
            continue
        entry = lib['downloads']['artifact']
        path = root / 'libraries' / entry['path']
        targets.append((entry, path))
        classpath.append(str(path))

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(download_entry, targets))
        # Fetch the complete vanilla asset index so the renderer can open all screens.
        objects = sorted({x['hash'] for x in json.loads(index.read_text())['objects'].values()})
        jobs = []
        for digest in objects:
            key = digest[:2] + '/' + digest
            jobs.append(({'url': 'https://resources.download.minecraft.net/' + key, 'sha1': digest},
                         assets / 'objects' / key))
        list(pool.map(download_entry, jobs))
    game = root / 'client-data'
    game.mkdir(exist_ok=True)
    (game / 'options.txt').write_text('soundCategory_master:0.0\nrenderDistance:4\nmaxFps:20\n')
    flags = ['-XstartOnFirstThread'] if sys.platform == 'darwin' else []
    return ['java', *flags, '-Xms256M', '-Xmx1536M', '--enable-native-access=ALL-UNNAMED',
            '-cp', os.pathsep.join(classpath), v['mainClass'],
            '--username', 'ParkourseViewer', '--version', '26.1.2', '--gameDir', str(game),
            '--assetsDir', str(assets), '--assetIndex', v['assetIndex']['id'],
            '--uuid', '4eae62d3c97b388a90f2a72a5bf35f2d', '--accessToken', '0', '--clientId', '0',
            '--xuid', '0', '--versionType', 'release', '--width', '800', '--height', '480',
            '--quickPlayMultiplayer', '127.0.0.1:25586']

def check_client():
    if not (root / 'source' / 'world' / 'level.dat').exists():
        raise RuntimeError('Headless setup must pass first')
    command = client_command()
    log = root / 'headful-server.log'
    server = start_server(root / 'run with spaces', log, root / 'source' / 'world')
    try:
        wait_for(log, lambda text: 'Done (' in text, server)
        client_log = root / 'headful-client.log'
        with client_log.open('w') as output:
            client = subprocess.Popen(command, env=dict(base_env, ALSOFT_DRIVERS='null'),
                                      stdout=output, stderr=subprocess.STDOUT)
        try:
            wait_for(log, lambda text: 'ParkourseViewer joined the game' in text, client)
            send(server, 'gamemode spectator ParkourseViewer')
            wait_for(log, lambda text: 'Spectator Mode' in text, server)
            jump()
            print(f'{platform.platform()}: graphical Minecraft joined and spectated while the bot ran.', flush=True)
        except Exception:
            print(client_log.read_text(errors='replace')[-6500:])
            raise
        finally:
            if client.poll() is None:
                client.terminate()
                client.wait(timeout=15)
    finally:
        stop(server)

{'server': check_server, 'client': check_client}[sys.argv[1]]()
