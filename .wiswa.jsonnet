local utils = import 'utils.libjsonnet';

(import 'defaults.libjsonnet') + {
  local top = self,
  want_main: true,

  authors: [
    {
      'family-names': 'Udvare',
      'given-names': 'Andrew',
      email: 'audvare@gmail.com',
      name: '%s %s' % [self['given-names'], self['family-names']],
    },
  ],
  description: 'Generate disk file paths for mkisofs that fit on certain size discs.',
  keywords: ['iso', 'media', 'optical'],
  project_name: 'gendisc',
  version: '0.0.1',

  local funding_name = '%s2' % std.asciiLower(self.github_username),
  github_username: 'Tatsh',
  github+: {
    funding+: {
      ko_fi: funding_name,
      liberapay: funding_name,
      patreon: funding_name,
    },
  },

  citation+: {
    'date-released': '2025-04-09',
  },

  pyproject+: {
    tool+: {
      poetry+: {
        dependencies+: {
          click: '^8.1.8',
          'python-fsutil': '^0.15.0',
          tqdm: '^4.67.1',
          wakepy: '^0.10.1',
          wand: '^0.6.13',
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
}
