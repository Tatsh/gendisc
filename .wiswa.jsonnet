local utils = import 'utils.libjsonnet';

{
  uses_user_defaults: true,
  description: 'Generate disk file path lists for mkisofs.',
  keywords: ['backup', 'iso', 'media', 'optical'],
  project_name: 'gendisc',
  version: '0.1.0',
  want_main: true,
  want_flatpak: true,
  publishing+: { flathub: 'sh.tat.gendisc' },
  pyinstaller+: {
    extra_args: ['--add-data', '"${project_name}/templates:${project_name}/templates"'],
  },
  pyproject+: {
    project+: {
      scripts+: {
        genlabel: 'gendisc.main:genlabel_main',
      },
    },
    tool+: {
      poetry+: {
        dependencies+: {
          anyio: utils.latestPypiPackageVersionCaret('anyio'),
          jinja2: utils.latestPypiPackageVersionCaret('jinja2'),
          'python-fsutil': utils.latestPypiPackageVersionCaret('python-fsutil'),
          rich: utils.latestPypiPackageVersionCaret('rich'),
          wakepy: utils.latestPypiPackageVersionCaret('wakepy'),
        },
        group+: {
          tests+: {
            dependencies+: {
              'pytest-asyncio': utils.latestPypiPackageVersionCaret('pytest-asyncio'),
            },
          },
        },
      },
      pytest+: {
        ini_options+: {
          asyncio_mode: 'auto',
        },
      },
      coverage+: {
        report+: {
          omit+: ['gendisc/typing.py'],
        },
        run+: {
          omit+: ['gendisc/typing.py'],
        },
      },
    },
  },
  vscode+: {
    settings+: {
      '[jinja-shell]': {
        'editor.tabSize': 4,
      },
    },
  },
  // Common
  authors: [
    {
      'family-names': 'Udvare',
      'given-names': 'Andrew',
      email: 'audvare@gmail.com',
      name: '%s %s' % [self['given-names'], self['family-names']],
    },
  ],
  local funding_name = '%s2' % std.asciiLower(self.github_username),
  github_username: 'Tatsh',
  github+: {
    funding+: {
      ko_fi: funding_name,
      liberapay: funding_name,
      patreon: funding_name,
    },
  },
  mastodon_id: '109370961877277568',
}
