#!/usr/bin/env python
#
# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Processes an Android AAR file."""

import argparse
import os
import posixpath
import re
import shutil
import sys
from xml.etree import ElementTree
import zipfile

from util import build_utils

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),
                                             os.pardir, os.pardir)))
import gn_helpers


def _IsManifestEmpty(manifest_str):
  """Returns whether the given manifest has merge-worthy elements.

  E.g.: <activity>, <service>, etc.
  """
  doc = ElementTree.fromstring(manifest_str)
  for node in doc:
    if node.tag == 'application':
      if len(node):
        return False
    elif node.tag != 'uses-sdk':
      return False

  return True


def _CreateInfo(aar_file):
  data = {}
  data['aidl'] = []
  data['assets'] = []
  data['resources'] = []
  data['subjars'] = []
  data['subjar_tuples'] = []
  data['has_classes_jar'] = False
  data['has_proguard_flags'] = False
  data['has_native_libraries'] = False
  data['has_r_text_file'] = False
  with zipfile.ZipFile(aar_file) as z:
    data['is_manifest_empty'] = (
        _IsManifestEmpty(z.read('AndroidManifest.xml')))

    for name in z.namelist():
      if name.endswith('/'):
        continue
      if name.startswith('aidl/'):
        data['aidl'].append(name)
      elif name.startswith('res/'):
        data['resources'].append(name)
      elif name.startswith('libs/') and name.endswith('.jar'):
        label = posixpath.basename(name)[:-4]
        label = re.sub(r'[^a-zA-Z0-9._]', '_', label)
        data['subjars'].append(name)
        data['subjar_tuples'].append([label, name])
      elif name.startswith('assets/'):
        data['assets'].append(name)
      elif name.startswith('jni/'):
        data['has_native_libraries'] = True
      elif name == 'classes.jar':
        data['has_classes_jar'] = True
      elif name == 'proguard.txt':
        data['has_proguard_flags'] = True
      elif name == 'R.txt':
        # Some AARs, e.g. gvr_controller_java, have empty R.txt. Such AARs
        # have no resources as well. We treat empty R.txt as having no R.txt.
        data['has_r_text_file'] = (z.read('R.txt').strip() != '')

  return """\
# Generated by //build/common/android/gyp/aar.py
# To regenerate, use "update_android_aar_prebuilts = true" and run "gn gen".

""" + gn_helpers.ToGNString(data)


def _AddCommonArgs(parser):
  parser.add_argument('aar_file',
                      help='Path to the AAR file.',
                      type=os.path.normpath)


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  command_parsers = parser.add_subparsers(dest='command')
  subp = command_parsers.add_parser(
      'list', help='Output a GN scope describing the contents of the .aar.')
  _AddCommonArgs(subp)
  subp.add_argument('--output',
                    help='Output file.',
                    type=argparse.FileType('w'),
                    default='-')

  subp = command_parsers.add_parser('extract', help='Extracts the .aar')
  _AddCommonArgs(subp)
  subp.add_argument('--output-dir',
                    help='Output directory for the extracted files.',
                    required=True,
                    type=os.path.normpath)
  subp.add_argument('--assert-info-file',
                    help='Path to .info file. Asserts that it matches what '
                         '"list" would output.',
                    type=argparse.FileType('r'))

  args = parser.parse_args()

  if args.command == 'extract':
    if args.assert_info_file:
      expected = _CreateInfo(args.aar_file)
      actual = args.assert_info_file.read()
      if actual != expected:
        raise Exception('android_aar_prebuilt() cached .info file is '
                        'out-of-date. Run gn gen with '
                        'update_android_aar_prebuilts=true to update it.')
    # Clear previously extracted versions of the AAR.
    shutil.rmtree(args.output_dir, True)
    build_utils.ExtractAll(args.aar_file, path=args.output_dir)

  elif args.command == 'list':
    args.output.write(_CreateInfo(args.aar_file))


if __name__ == '__main__':
  sys.exit(main())
