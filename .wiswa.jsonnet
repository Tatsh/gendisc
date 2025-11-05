local utils = import 'utils.libjsonnet';

{
  description: 'Generate disk file path lists for mkisofs.',
  keywords: ['backup', 'iso', 'media', 'optical'],
  project_name: 'gendisc',
  version: '0.0.13',
  want_main: true,
  citation+: {
    'date-released': '2025-05-26',
  },
  copilot+: {
    intro: 'gendisc generates disk file path lists for mkisofs.',
  },
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
          jinja2: utils.latestPypiPackageVersionCaret('jinja2'),
          'python-fsutil': utils.latestPypiPackageVersionCaret('python-fsutil'),
          tqdm: utils.latestPypiPackageVersionCaret('tqdm'),
          wakepy: utils.latestPypiPackageVersionCaret('wakepy'),
        },
        group+: {
          dev+: {
            dependencies+: {
              'types-tqdm': utils.latestPypiPackageVersionCaret('types-tqdm'),
            },
          },
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
