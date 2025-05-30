(import 'defaults.libjsonnet') + {
  // Project-specific
  description: 'Generate disk file path lists for mkisofs.',
  keywords: ['backup', 'iso', 'media', 'optical'],
  project_name: 'gendisc',
  version: '0.0.13',
  want_main: true,
  citation+: {
    'date-released': '2025-05-26',
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
          jinja2: '^3.1.6',
          'python-fsutil': '^0.15.0',
          tqdm: '^4.67.1',
          wakepy: '^0.10.1',
        },
        group+: {
          dev+: {
            dependencies+: {
              'types-tqdm': '^4.67.0.20250319',
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
