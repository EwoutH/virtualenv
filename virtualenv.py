"""Create a "virtual" Python installation
"""

import sys
import os
import optparse
import shutil
try:
    import subprocess
except ImportError, e:
    if sys.version_info <= (2, 3):
        print 'ERROR: %s' % e
        print 'ERROR: this script requires Python 2.4 or greater; or at least the subprocess module.'
        sys.exit(101)
    else:
        raise
    
join = os.path.join
py_version = 'python%s.%s' % (sys.version_info[0], sys.version_info[1])

## FIXME: probably other modules for Windows?
REQUIRED_MODULES = ['os', 're', 'posix', 'posixpath', 'stat', 'UserDict', 'readline',
                    'copy_reg', 'types', 'fnmatch',
                    'sre', 'sre_parse', 'sre_constants', 'sre_compile']

class Logger(object):

    FATAL = 1
    ERROR = 2
    WARNING = 3
    NOTIFY = 4
    INFO = 5
    DEBUG = 6

    DEFAULT = 4

    def __init__(self, level):
        self.level = level

    def fatal(self, msg, *args, **kw):
        self.log(self.FATAL, msg, *args, **kw)
    def error(self, msg, *args, **kw):
        self.log(self.ERROR, msg, *args, **kw)
    def warning(self, msg, *args, **kw):
        self.log(self.WARNING, msg, *args, **kw)
    warn = warning
    def notify(self, msg, *args, **kw):
        self.log(self.NOTIFY, msg, *args, **kw)
    def info(self, msg, *args, **kw):
        self.log(self.INFO, msg, *args, **kw)
    def debug(self, msg, *args, **kw):
        self.log(self.DEBUG, msg, *args, **kw)
    def log(self, level, msg, *args, **kw):
        if level <= self.level:
            if args and kw:
                raise TypeError(
                    "positional or keyword arguments allowed; not both")
            if args:
                msg = msg % args
            elif kw:
                msg = msg % kw
            print msg

def mkdir(path):
    if not os.path.exists(path):
        logger.notify('Creating %s', path)
        os.makedirs(path)
    else:
        logger.info('Directory %s already exists', path)

def copyfile(src, dest):
    if not os.path.exists(src):
        # Some bad symlink in the src
        logger.warn('Cannot find file %s', src)
        return
    if os.path.exists(dest):
        logger.info('File %s already exists', dest)
        return
    if hasattr(os, 'symlink'):
        logger.info('Symlinking %s', dest)
        os.symlink(src, dest)
    else:
        logger.info('Copying to %s', dest)
        if os.path.isdir(src):
            shutil.copytree(src, dest, True)
        else:
            shutil.copy2(src, dest)

def writefile(dest, content):
    if not os.path.exists(dest):
        logger.info('Writing %s', dest)
        f = open(dest, 'wb')
        f.write(content)
        f.close()
        return
    else:
        f = open(dest, 'rb')
        c = f.read()
        f.close()
        if c != content:
            logger.notify('Overwriting %s with new content', dest)
            f = open(dest, 'wb')
            f.write(content)
            f.close()
        else:
            logger.info('Content %s already in place', dest)

def rmtree(dir):
    if os.path.exists(dir):
        logger.notify('Deleting tree %s', dir)
        shutil.rmtree(dir)
    else:
        logger.info('Do not need to delete %s; already gone', dir)

def make_exe(fn):
    if os.name == 'posix':
        oldmode = os.stat(fn).st_mode & 07777
        newmode = (oldmode | 0555) & 07777
        os.chmod(fn, newmode)
        logger.info('Changed mode of %s to %s', fn, oct(newmode))

def install_setuptools(py_executable):
    setup_fn = 'setuptools-0.6c7-py%s.egg' % sys.version[:3]
    setup_fn = join(os.path.dirname(__file__), 'support-files', setup_fn)
    cmd = [py_executable, '-c', EZ_SETUP_PY]
    if os.path.exists(setup_fn):
        logger.info('Using existing Setuptools egg: %s', setup_fn)
        cmd.append(setup_fn)
    else:
        logger.info('No Setuptools egg found; downloading')
        cmd.extend(['--always-copy', '-U', 'setuptools'])
    logger.notify('Installing setuptools')
    subprocess.call(cmd)

def main():
    parser = optparse.OptionParser(
        usage="%prog [OPTIONS] DEST_DIR")

    parser.add_option(
        '-v', '--verbose',
        action='count',
        dest='verbose',
        default=0,
        help="Increase verbosity")

    parser.add_option(
        '-q', '--quiet',
        action='count',
        dest='quiet',
        default=0,
        help='Decrease verbosity')

    parser.add_option(
        '--clear',
        dest='clear',
        action='store_true',
        help="Clear out the non-root install and start from scratch")

    parser.add_option(
        '--no-site-packages',
        dest='no_site_packages',
        action='store_true',
        help="Don't copy the contents of the global site-packages dir to the "
             "non-root site-packages")

    if 'extend_parser' in globals():
        extend_parser(parser)

    options, args = parser.parse_args()

    global logger

    if 'adjust_options' in globals():
        adjust_options(options, args)

    verbosity = options.verbose - options.quiet
    logger = Logger(Logger.DEFAULT + verbosity)

    if not args:
        print 'You must provide a DEST_DIR'
        parser.print_help()
        sys.exit(2)
    if len(args) > 1:
        print 'There must be only one argument: DEST_DIR (you gave %s)' % (
            ' '.join(args))
        parser.print_help()
        sys.exit(2)

    home_dir = args[0]

    if os.environ.get('WORKING_ENV'):
        logger.fatal('ERROR: you cannot run virtualenv while in a workingenv')
        logger.fatal('Please deactivate your workingenv, then re-run this script')
        sys.exit(3)

    create_environment(home_dir, site_packages=not options.no_site_packages, clear=options.clear)
    if 'after_install' in globals():
        after_install(options, home_dir)

def create_environment(home_dir, site_packages=True, clear=False):
    """
    Creates a new environment in ``home_dir``.

    If ``site_packages`` is true (the default) then the global
    ``site-packages/`` directory will be on the path.

    If ``clear`` is true (default False) then the environment will
    first be cleared.
    """
    if sys.platform == 'win32':
        lib_dir = join(home_dir, 'lib')
    else:
        lib_dir = join(home_dir, 'lib', py_version)
    inc_dir = join(home_dir, 'include', py_version)
    bin_dir = join(home_dir, 'bin')

    if sys.executable.startswith(bin_dir):
        print 'Please use the *system* python to run this script'
        return
        
    if clear:
        rmtree(lib_dir)
        rmtree(inc_dir)
        ## FIXME: why not delete it?
        logger.notify('Not deleting %s', bin_dir)

    prefix = sys.prefix
    mkdir(lib_dir)
    stdlib_dir = join(prefix, 'lib', py_version)
    for fn in os.listdir(stdlib_dir):
        if fn != 'site-packages' and os.path.splitext(fn)[0] in REQUIRED_MODULES:
            copyfile(join(stdlib_dir, fn), join(lib_dir, fn))
    mkdir(join(lib_dir, 'site-packages'))
    writefile(join(lib_dir, 'site.py'), SITE_PY)
    writefile(join(lib_dir, 'orig-prefix.txt'), prefix)
    site_packages_filename = join(lib_dir, 'no-global-site-packages.txt')
    if not site_packages:
        writefile(site_packages_filename, '')
    else:
        if os.path.exists(site_packages_filename):
            logger.info('Deleting %s' % site_packages_filename)
            os.unlink(site_packages_filename)

    #mkdir(inc_dir)
    #stdinc_dir = join(prefix, 'include', py_version)
    #for fn in os.listdir(stdinc_dir):
    #    copyfile(join(stdinc_dir, fn), join(inc_dir, fn))

    if sys.exec_prefix != sys.prefix:
        exec_dir = join(sys.exec_prefix, 'lib', py_version)
        for fn in os.listdir(exec_dir):
            copyfile(join(exec_dir, fn), join(lib_dir, fn))

    mkdir(bin_dir)
    logger.notify('Copying %s to %s', sys.executable, bin_dir)
    py_executable = join(bin_dir, 'python')
    if sys.executable != py_executable:
        ## FIXME: could I just hard link?
        shutil.copyfile(sys.executable, py_executable)
        make_exe(py_executable)
    cmd = [py_executable, '-c', 'import sys; print sys.prefix']
    logger.info('Testing executable with %s %s "%s"' % tuple(cmd))
    proc = subprocess.Popen(cmd,
                            stdout=subprocess.PIPE)
    proc_stdout, proc_stderr = proc.communicate()
    proc_stdout = os.path.abspath(proc_stdout.strip())
    if proc_stdout != os.path.abspath(home_dir):
        logger.fatal(
            'ERROR: The executable %s is not functioning' % py_executable)
        logger.fatal(
            'ERROR: It thinks sys.prefix is %r (should be %r)'
            % (proc_stdout, home_dir))
        logger.fatal(
            'ERROR: virtualenv is not compatible with this system or executable')
        sys.exit(100)
    else:
        logger.info('Got sys.prefix result: %r' % proc_stdout)

    pydistutils = os.path.expanduser('~/.pydistutils.cfg')
    if os.path.exists(pydistutils):
        logger.notify('Please make sure you remove any previous custom paths from '
                      'your %s file.' % pydistutils)

    install_setuptools(py_executable)

def create_bootstrap_script(extra_text):
    """
    Creates a bootstrap script, which is like this script but with
    extend_parser, adjust_options, and after_install hooks.

    This returns a string that (written to disk of course) can be used
    as a bootstrap script with your own customizations.  The script
    will be the standard virtualenv.py script, with your extra text
    added (your extra text should be Python code).

    If you include these functions, they will be called:

    ``extend_parser(optparse_parser)``:
        You can add or remove options from the parser here.

    ``adjust_options(options, args)``:
        You can change options here, or change the args (if you accept
        different kinds of arguments, be sure you modify ``args`` so it is
        only ``[DEST_DIR]``).

    ``after_install(options, home_dir)``:

        After everything is installed, this function is called.  This
        is probably the function you are most likely to use.  An
        example would be::

            def after_install(options, home_dir):
                subprocess.call([join(home_dir, 'bin', 'easy_install'),
                                 'MyPackage'])
                subprocess.call([join(home_dir, 'bin', 'my-package-script'),
                                 'setup', home_dir])

        This example immediately installs a package, and runs a setup
        script from that package.
    """
    filename = __file__
    if filename.endswith('.pyc'):
        filename = filename[:-1]
    f = open(filename, 'rb')
    content = f.read()
    f.close()
    return content.replace('##EXT' 'END##', extra_text)

##EXTEND##

##file site.py
SITE_PY = """
eJytW3tz2ziS/5+fAiNXipJHpvO43dpKxnOVh2fHV87jJpna1DouLUVCFmIK4BBkZO3VfffrB0CC
pJQ4t6tKxTYJNBrdv34Cmkwmz8tS6lxsTN4UUliZVtlalGm9tmJlKlGvVZWflGlV7+BpdpveSCtq
I+zOJjgqiaLjf/ETHYsPa2U9C/Bb2tRmk9YqS4tiJ9SmNFUtc5E3ldI3QmlVq7RQ/4QRRifi+F/n
ILrQAnZeKFmJL7KyQNcKsxLvdvXaaDFtStzzo+RP6ZPZXNisUmUNAyrHM0hkndaRljIHNmFkY0GU
qpYntpSZWqmsHbg1TZGLskgzKf7xD94aDY3jyJqN3K5lJYUGZoCmBFol8gG/qkpkJpeJEC9kluIC
/LwTVsTU5qgzi2LURhRG38CetMyktWm1E9NlUxMhYlnkBnhSwEGtiiLamurWzkClpI8tPBIpw6O/
GYYH7BPXHyMHeHyro9+1upszbUAPkqvXDJtKrtSdSJEs/CnvZLZwz6ZqJXK1WoEMdD3DIREzYEWh
lqclqeMnp6GfT4mrFpUprCGRZR7ML2lGEr3VwgCzFUq+BlxvrJhuUqUBXq/TjHj5m9K52doZ8Qzy
teJzY+uA42i6h2UYHbA8FyheL/9GF+pWFrsZCOTDWkaVtE1RI4RzVcmsNpWSlggAazsh75QFCino
nzfNWPKWNmdxFNaABaAq0CTQRPElqFSv1E1TkU2IlQKsgR5/efubeHX+4uL5G4cKT4yt7GYDPAMV
Uk3AEywgThtbnRYGTDCJLvGHSPMczeIG1we+ugGn39RNNIW9l8lwTqAiEPsruVSp9svAHmswf1or
onn/A1Pmdg3y+d+vrwYbf35IKrRx/m27NmBFOt1IsU4tYRmREf3k6PyclPX6GaDBIp0aRGVZOXmu
kB6IJJTZ1GgpSoBYobScRSChJY3taxGg8MboE9L1AAlAoYo0vAyezWhFLWGjY1rP0ML94B3tzA2J
Wj1vTEWmDvjXGXmPItW3xKMl2PNvS3mjtEaGEAtRfBTTwvZWARLzRFzSKLJkP0jE7G94JJpEA1hC
0AEm5V26KQsJvrIpSxTzNwyfFpO18LouGHEwsiaHSFrrtroXe4+TJwPUEZv1upJAvFn2jG5lDBgr
eFnipkw3c15tawg50R57okmICRoJc/F3kOhza5uNbF8iVsCzEKCilSkKswWRPY0iIY5wkA+jfXDC
W3gH/wNd/L+QdbaOomCllrAjhcwfIoVEwIlL7VDtmOihzUF56GSUZk9hqlxWtNT9hH3KjN9zMO41
emNqF4Z4u6hls1E1uqSlC3KKY5SOa/aPz3jfsA2ItZZk5od2ctrg9opynS6lTyKWcoWW4JT0rFU7
rBntWZOiZy3QP4JE4R2IRSqOIPsdCzqdVS0pbAMNNr5Uq7IpaJBFgIkUFtqURH+TYhA2Lr0BeHMg
jdAhccDNIP4Ab/8EM9quFcgnAwrgYdBLgfqWqq4wpHf+KOqHaT+f1wekXqxcbOIlV6kqXFxOdXRB
D8+risw3kyXOmjthWNihrjEZu9EgRzTzyWQSRT6B2Vn/q2l/WyyWjcJ4t1hEUS5XsONbiXKZHlMC
MXsKeBGISXEG09g9pktLQ/zfn43SfvyMxleybiqN0+btLOBpk6VWTuHpjBcDQosFKmaxmLqVgOP3
4GMwqrCsY+GHoGIqBcGbVIKKWlpT4J9IH7eKBDDabhAKaC4uo0u+pEUjrV8DP3W16/7AzyZp1xnv
tHs5ayex/MVzzxRppU8TvYHSjeTdVnJjvsgcnC1KKtiw+I3eQO5cFmAKsCHQI9n/qjKbLh9IMVNk
LICa0FcAjjdExYvCS+GI03WpbVO51JfcjMvLGfplZb4odC7LnXsJtgFmixbiHZmjZjAL68kbTQDs
BaKexuxoK2Mw3arhAEV8I0lEV94FhYTIXYKEr67p11tttnrBueoZRpfprNUigs7pEQd0oj0SvwBm
gUkDiVwnNKYCIV4gzE6Aedg+bBckS7kEEALDRq9jTUDLp3a0Rc4ScVmkMXsmCMeVRP/wxS9BqZUX
RkCJ3ibtA0I//IeUYHOtZRH+/SBYHZ2YHwYLByLpo+ky4ZSzT2AgxQQ8zdRR40FefldPr4GLy9A+
g3lRdCQ+fvzIsLFrqoCQsSVuGl3GitxdUu4gX1CQpngPzPUUwQDqIg1kGuugKU7eC1Oy9wV9cqEG
Lu49xPp1XZdPT0+3223i8n9T3Zza1emf/vLnP//lIbuHPCf8wHYCa3HFcHJK7zCCJT/5iuFnr7kB
HpXuo5FoTSV5YQo9yN9fG5Ub8fRk1roSRHEOAa2Byssm+L93yzeyXvhFWcog20nH0QN78iB5Yifi
gZiGY6dYmoJCXFI8a+f2fKn/AzhFM5u2Kjx5dI0E+or1sLDOqy7QyEmrSq9MILnfWOspZXHOwFE6
6GxHye5uvxPyssnvb64jVwuY9ztUFpWLgO4Pubf9tIPHwMePc9IfduVX/XNgE3nksecSoSninnhB
XcxDowlAmecgVy237FnBP4SeDfwrJDxLlrYjR9lNjCRjQdGccnNWrBsBchqU5j6d91qAEeE6YI9Q
uMhuk0MotC8gKAAGzsQjeiILG0zy7x6yapuioPprgNGeVJhwT9ErnAC4nHoCczGpfp/wSKeWi7cD
pbAO9hAzXLIhwFYjMOGbhMWEUppOjiZ74NRT9tdms4z3kUAl0fj7ESeOz3iByoIxldM+cA8hvJUt
l6kDhg/HC8KU1xJZtD1gW0PfsdemvhpWVkqj5wx0lGQFVJFui2rFOOre90M94vRgKHIG6MTQiSMY
dIYE+vYXu3FY7N40WBaEVRNytFGWYhOKCcrtHJICqkaodARZErWWzH2NrL+xf4PJtft1vxyARyto
BEQ49FASMQoYjo5/fyRQjK52AiPQIMKxLVLix96gAIQFCurZNryWB42baCQWzCwIIORlgHd62U3D
DcKTBDuMZKBI+a62shQ/igmob2ip93Pd/1aU+pp5GgygQO96J2dda2Uugp7K2aDH0gd0v3VKnc3S
AIKXkLCEbbkQ5h60TI8UddX32y1T4JCpCTCZhaxee8GErZ8fzoIRnbD8Ih5QvYV6DVi/UqdtRxn0
7an0VD5cyj2mbbpcCudOY2Mfy81dPBdxpWxmbLzP2zEMxsJo2btUywn86El8MrvuUZIFJy6IvLMz
EZ/G37/SaMLBz6RAlr5jPINhAkYRJJhXT59cfw+RgQC+PnW/KItQlMzTQJD4GSWF/nNE7EPObJaf
IRG1rvT8kqoiXRbkIE5O0A8A8VwumxvO6vfS6lPaP8QpLMFyEdzRw/neNMdePbwGiNGC8WwcKu/R
DPCfMrV2gKswFAwZQyR52d5D4AewOzQdxG+eVlul94D4iAx0VYHPxNMmFrAVx6iJY6is0OtRPQVZ
kwYquYCarBgnRUcCrd41tl42VcXtKVJoKauTBiTOpzGnYH/cJ9NjTR6J0zeyRk7aYRnVp0Hv3oxm
wY5jV3G2O4k7d7NfN2vjE12pv6gK5gJ8pvGvb1+fx2Olu2Vw0n5yoR69j7y/RSHd77Dd2Akn/p45
LKHvmfL/dy5xD6FDK0LItYWPbsU2FuyoevTZx34dfCOP7PUrKdxzYIek4MX5Xy/eXF68ePf8w69B
Ff0BgP/2/eljcf76o6BmAJ5McZ8jxUK6xraT0b1zZ5Eb+NegA8ubesc9OyteXV66wL7Bc0xsbKNd
JfCce1YttRkJiM9H24eu2YQcFc4ygiNe6s3QETAayoYPK61xzW86OV5it71xNueO7v0RP1VBiRC/
w+BQFEyC+4nwio4oau8OKk4Y3bH3HqaSyMuR1ywKYnVYXAbpko/NQOwk3+nCpLmrIuFJN9kZ7FUc
8hpfJ7YsFJjws7jN+Nw0bKZ0kHEP23qI+ZrtydWD6bCyG8i7PsgFDAQOeG9u/qwD2h8NcNgB7BXs
W0tqJlBzHjuZIsZBMTcNoLKr41b1TgcWFIZ5YY1K9KBTsPsUvKqAYgRScg2+aouAQAoDTfRzm6dB
WMDBuAEEwstNfvLfSAHZSWInnv7cT58OTa6r4uTvoiwaK1wvyvMS7xH0aOorMVWJTMT5219mg5nB
OUaCrGEhFjxypPAHiD0rIASLxbuKGt5TTg86+dPTNOOGb2XwKMjnIpy4Kl37DmehMjBFsFqwyTnI
GSsiQD+Rwp4AZQOmsv6YFB6Wu0rdrGus2mByQkc0OPz184+XF2/O3wOfj5/wI+rmcUG5mFpZrHwh
k6d1Ouey9Qxbiugp4ZfABeLoZLFwnRv8MXyFNBDA8GP4iuvhM15gNI+TEvwxfMXn1K5sCnYAGG9K
2sCsl+SH0/reO6gViQzz2pZj+Al7jh1nfTKUx+CxmCstw/2Nw0U7cuCNKGb4l+M04GAquyqdDKd+
ctgDG37cHldlUsk0n+4fBG/DLsvws4Spt4eS01G3LfyMslK8MgMcjUf31/D9qNFQt50AbIfQgu+8
m/6kgzwrGJdptF8Q4jScPAtBVsmycmYytgNGYO/YZURM/OTY9Za4D5Ji8klPXJDqcdIKe5TN+4nY
hBYP7JTrdcmhHruj8JAcCJ0WTAPLnc+OH/f2iOfk996j813gQX8F7+ccLh2PmgqQCL/8wbkHv5p5
t/5UxEGw01KbtjOFn+0aE5NH/T3utQFcS6HZVam+kVOmNfc0f+wL+0D6Rt62h5grNSjLHbohvbk7
APCxWeyvuTxnAxyMxt3K3dAb9aWDA0Z9wjGFKt2Cdy+besq6Olhi4HA0M+p4YK/jj31tjnuw52hh
mP5jT+WHHxaWz03aeDU4oI/bFy4pySrIrWtLJVYQen16EUbjLgaedVF40j6d8BFZ+3ebuIUV7NXT
/7imbXxOv6TBTnrrMEvhKr0dT9yAQZtl8l98o5Tufyg6JevOyN27XH6RhYEiFtJ3PMP83J5hzpLJ
vqzxG3x1rKCAP7ncLtW3lL+//NvFXLx88xv8/0K+hQQVhLOZi78DA+KlqSBR5zsuqIgUzz9rzsBN
Y+GRbXtudNGLb4e96+0Dm+XuYLZ/Itv6C4Hd7GrD13mBRd4j3fvqoqU/r4S/+/clwt37lGmfVibu
JYrh8CkxnqyeupHJut4U6DiDurRT59Xk8uLl+Zv350l9h7jyf06CurXfp8MduUZLhUXlXLRPsgaf
XM+6DPJXWZR7EkiXwPsTZ0zgRbyGsW3SzndPU7GtsN6oIIHHKkyUu9xkCY4EVNGVH1FvIaOcBbn6
NyNeL9wgrSnXjmFai49BGuLT0ANMYCDNcXuimcRQusTbFvw4meyPSXNxnFY3Fn4c325zGyZ7fGxO
Gxxy2u162p/eOqE1y9nRC8FErJ21mvD3igqV2s0yCy/ZvNX+9jC4F2zzwMC0KWohdWZyqpnoGid4
2fBeDNsJo4V9O10Woaq32KY7G7QmoaCf4KoTuomWQsVLXW+oWF6nt+yL8cIOlPk0HKgTo1RLmGCq
bbI12zGXB3vcH7m+rdJPHscjIfOic7pBnnVJHewTUyjm6EbWbv/8YDq7etSFVez+6yw8FI2zEiJO
iJQjcJ/l8fHxRPzntzMBZiUpjLmFFAVo9yOdC+GX9PpADHeba7U1znL9mwQgma3lFTzAwjt43mjq
/HxlKilEtj89jRh1E7d49OMHMZF7INRE8SOwpdPGjt+1olv9WKlLdLnuyxF08RzpeEiCb4hTmykV
c3sU9LEzDV5owa6Nw4u8A8SrDd1oh7d48ZDLzjVmW3SJsEVPy86ZmBDhCejvlVuNLsfRnRDgc/Fu
59hcXGhVd6e5D8P7V+eaEIx5LIcUhyuRbtEy/D4GwgjuRvWg2mWb5qsQ7WXvJrsK+zeDXfLrb/EO
0AZLM6uV5xQeeiVlRlaZD6qoMZWpOiDjxyEdngz1vgtASbSHpQl4eAoMeWvR7dsfWr2EnL6ljuSJ
X8m14ev2ex9VqrD5owfHDknSrY8+w7aCbHHrf5nBKm+oS+jygd5a4gfXo8KjvN5l1/BSUaPdJVbq
2YruZivQoS9OtA6yhWPPRwTfr2npM2hdYt/deQ1OHrFcJd6+qKpu0mLhvouwwJRt0Z7HOj7byyhf
vWbV5iyQYBtIPU+4BYm5g+9WozwhPy78wSjU665cT8ILHv27EO25uztjejQ8Y+oThdULtcQsn3Oe
+MdBz30262/9K4fQbv+uSh9cDbm3MLQ5uSnMMi1O+t/hYMGMUo/vORQP9r0vbT507o5a9sr9BgJo
TO+mccQIAmIwZwFcYCk2uJzrxYZy4Z4QmGhprLqbtF+O4Eu5wYmVl+ESYsf44h6ReM2HAuGdhd41
x328DeUZvt474RAwxhP3pRXuRD3sLwzOQiL3lBvX/q+gVPSPfOLGOuiyMv++C6TO4kd+JmJX6G5I
H3Bns/ZMAo8ULYZChHsbCaWj0vrblL4FMPySIh2k1BKqJ3dBAbSYyeCWK11wZVJ1/9uQFXjBFDN6
/t7hvP2eAo3jqG/bL+BgVp/JxGtgnVq82o5owXPc0f5CsOSyOCCFKGKjcJdAcR/eQriJMmkxewaF
UVsUHry36Wbhrw+qOTWnsBM6C0le4/cLsApAuOPVecDPgi1w4RDkOIn+D9Tw0Mw=
""".decode("base64").decode("zlib")

##file ez_setup.py
EZ_SETUP_PY = """
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
""".decode("base64").decode("zlib")

if __name__ == '__main__':
    main()
