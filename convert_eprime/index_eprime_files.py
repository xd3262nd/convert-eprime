# emacs: -*- mode: python-mode; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 et:
"""
Created on Thu May 22 14:09:37 2014
Designed to check for the existence of paired edat/text files in a folder.
It will flag text files that do not have a paired edat or which have a paired
text (two text files).
Somewhat functional, but barely readable, as of 150209.
@author: tsalo
"""
from __future__ import print_function
import re
import os
import sys
import time
import json
import shutil
from glob import glob

import pandas as pd

note_dict = {
    'one_text': 'One text file- must be recovered.',
    'two_texts': 'Two text files- must be merged.',
    'three_files': 'One edat and two text files- it\'s a thinker.',
    'pair': 'All good.',
    'one_edat': 'One edat- unknown problem.',
    }

global note_dict


def add_subject(df, subj, timepoint, orged, orgedwhen, orgedby, conved,
                convedwhen, convedby, notes):
    """
    Adds information about subject's data to spreadsheet.
    """
    row = pd.DataFrame([dict(Subject=subj, Timepoint=timepoint,
                             Organized=orged, Date_Organized=orgedwhen,
                             Organized_by=orgedby, Converted=conved,
                             Date_Converted=convedwhen, Converted_by=convedby,
                             Notes=notes)])
    df = df.append(row, ignore_index=False)
    return df


def get_subject(text_file):
    """
    Splits file name by hyphens to determine subject ID.
    """
    path_name, _ = os.path.splitext(text_file)
    fname = os.path.basename(path_name)
    fname = fname.replace('-Left_Handed', '')
    all_hyphens = [m.start() for m in re.finditer('-', fname)]
    if len(all_hyphens) == 1:
        beg = fname[:len(fname)-2].rindex('_')
    else:
        beg = all_hyphens[-2]

    end = all_hyphens[-1]
    subj = fname[beg+1:end]
    subj = subj.lower()

    return subj


def get_timepoint(text_file):
    """
    Splits file name by hyphens to determine timepoint.
    """
    path_with_filename, _ = os.path.splitext(text_file)
    fname = os.path.basename(path_with_filename)
    fname = fname.replace('-Left_Handed', '')

    # I forget what this does.
    all_underscores = [m.start() for m in re.finditer('_', fname)]
    last_hyphen = fname.rindex('-')
    if not all_underscores:
        timepoint = fname[-1]
    elif all_underscores[-1] < last_hyphen:
        timepoint = fname[-1]
    else:
        timepoint = fname[all_underscores[-1]]

    return timepoint


def organize_files(subject_id, timepoint, files, organized_dir):
    """
    If there are no problems, copies edat and text files with known subject ID
    and timepoint to organized directory and moves those files in the raw data dir
    to a 'done' subfolder.

    If the file already exists in the destination directory, it does not copy or
    move the file and returns a note to that effect.
    """
    note = ''
    for file_ in files:
        orig_dir, file_name = os.path.split(file_)

        # Create the destination dir if it doesn't already exist.
        org_dir = os.path.join(organized_dir, subject_id, timepoint)
        if not os.path.exists(org_dir):
            os.makedirs(org_dir)

        # If the file does not exist in the destination dir, copy it there and
        # move the original to a 'done' subdir.
        # If it does, return a note saying that the file exists.
        if os.path.isfile(org_dir + file_name):
            note += 'File {0} already exists in {1}. '.format(file_name, org_dir)
        else:
            shutil.copy(file_, org_dir)
            out_dir = os.path.join(orig_dir, 'done', os.sep)
            if not os.path.exists(out_dir):
                os.makedirs(out_dir)
            shutil.move(file_, out_dir)

    return note


def main(directory, csv_file, param_file):
    """
    This does so much. It needs to be documented.
    """
    # Read in data
    df = pd.read_csv(csv_file)
    with open(param_file, 'r') as file_object:
        param_dict = json.load(file_object)

    columns = df.columns.tolist()

    edat_files = glob(os.path.join(directory, '*.edat*'))  # Grab edat and edat2 files
    text_files = glob(os.path.join(directory, '*-*.txt'))  # Text files need - for timepoint
    all_files = edat_files + text_files
    pairs = []
    paired_texts = []

    for text_file in text_files:
        [text_fname, _] = os.path.splitext(text_file)
        for edat_file in edat_files:
            [edat_fname, _] = os.path.splitext(edat_file)
            if text_fname == edat_fname:
                pairs.append([text_file, edat_file])

    for pair in pairs:
        paired_texts.append(pair[0])

    unpaired_texts = list(set(text_files) - set(paired_texts))
    three_files = []
    pop_idx = []

    # Find text files that correspond to a pair.
    for i, up_text in enumerate(unpaired_texts):
        for j, p_text in enumerate(paired_texts):
            if up_text[:len(up_text)-6] in p_text:
                three_files.append([p_text, pairs[j][1], up_text])
                pop_idx.append(i)

    # Remove files with buddies from list of unpaired files.
    for rem_idx in reversed(pop_idx):
        unpaired_texts.pop(rem_idx)

    # three_files is the text files and edats that form a triad (one edat, two
    # similarly named text files).
    for triad in three_files:
        for i_pair in reversed(range(len(pairs))):
            if triad[0:2] == pairs[i_pair]:
                pairs.pop(i_pair)

    # Find pairs of similarly named text files.
    two_texts = []
    all_two_texts = []
    two_text_pairs = []
    for i, up_text1 in enumerate(unpaired_texts):
        for j in range(i + 1, len(unpaired_texts)):
            up_text2 = unpaired_texts[j]
            if up_text1[:len(up_text1)-6] in up_text2:
                all_two_texts.append(i)
                all_two_texts.append(j)
                two_text_pairs.append([i, j])

    all_two_texts = sorted(all_two_texts, reverse=True)

    # two_texts is the text files that pair with other text files.
    for tt_pair in two_text_pairs:
        two_texts.append([unpaired_texts[tt_pair[0]], unpaired_texts[tt_pair[1]]])

    for i_file in all_two_texts:
        unpaired_texts.pop(i_file)

    # one_text is the remaining un-paired text files. Place these in a list of
    # lists to match the format of the other file lists.
    one_text = [[f] for f in unpaired_texts]

    # Determine subject IDs and timepoints for all files.
    # Assumes that files will be named according to convention
    # blahblahblah_[subj]-[tp].txt or blahblahblah-[subj]-[tp].txt.
    one_text_subjects = [get_subject(f[0]) for f in one_text]
    one_text_timepoints = [get_timepoint(f[0]) for f in one_text]
    two_text_subjects = [get_subject(pair[0]) for pair in two_texts]
    two_text_timepoints = [get_timepoint(pair[0]) for pair in two_texts]
    three_file_subjects = [get_subject(triad[0]) for triad in three_files]
    three_file_timepoints = [get_timepoint(triad[0]) for triad in three_files]
    pair_subjects = [get_subject(pair[0]) for pair in pairs]
    pair_timepoints = [get_timepoint(pair[0]) for pair in pairs]

    # Place all accounted-for files in one list
    af_files = ([item for sublist in pairs for item in sublist] +
                [item for sublist in two_texts for item in sublist] +
                [item for sublist in three_files for item in sublist] +
                [item for sublist in one_text for item in sublist])

    # one_edat lists the edat files without an associated text file. I'm not
    # sure what would cause this situation to occur, so they're catalogued with
    # their own message.
    one_edat = list(set(all_files) - set(af_files))
    one_edat = [[edat] for edat in one_edat]
    one_edat_subjects = [get_subject(f[0]) for f in one_edat]
    one_edat_timepoints = [get_timepoint(f[0]) for f in one_edat]

    all_subjects = (one_text_subjects + two_text_subjects + three_file_subjects +
                    pair_subjects + one_edat_subjects)
    all_notetype = ((['one_text'] * len(one_text_subjects)) +
                    (['two_texts'] * len(two_text_subjects)) +
                    (['three_files'] * len(three_file_subjects)) +
                    (['pair'] * len(pair_subjects)) +
                    (['one_edat'] * len(one_edat_subjects)))
    all_timepoints = (one_text_timepoints + two_text_timepoints +
                      three_file_timepoints + pair_timepoints +
                      one_edat_timepoints)
    all_file_sets = one_text + two_texts + three_files + pairs + one_edat

    # Where organized files will be outputted
    organized_dir = param_dict.get('org_dir')

    for i_subj in range(len(all_subjects)):
        month = param_dict.get('timepoints').get(all_timepoints[i_subj])
        files_note = note_dict.get(all_notetype[i_subj])
        if len(all_subjects) > 4:
            try:
                print('Successfully organized {0}-{1}'.format(all_subjects[i_subj], month))
                print('Moved:')
                subject_id = all_subjects[i_subj]
                files = all_file_sets[i_subj]
                note = organize_files(subject_id, month, files, organized_dir)
                note.append(files_note)
                orged = True
                orgedwhen = time.strftime('%Y/%m/%d')
                orgedby = 'PY'
            except IOError:
                print('{0}-{1} couldn\'t be organized.'.format(all_subjects[i_subj],
                                                               all_timepoints[i_subj]))
                note = files_note
                orged = False
                orgedwhen = ''
                orgedby = ''

            try:
                if all_notetype[i_subj] == 'pair':
                    print('Successfully converted {0}-{1}'.format(all_subjects[i_subj],
                                                                  all_timepoints[i_subj]))
                    conved = True
                    convedwhen = time.strftime('%Y/%m/%d')
                    convedby = 'PY'
                else:
                    print('{0}-{1} couldn\'t be converted.'.format(all_subjects[i_subj],
                                                                   all_timepoints[i_subj]))
                    conved = False
                    convedwhen = ''
                    convedby = ''
            except IOError:
                print('{0}-{1} couldn\'t be converted.'.format(all_subjects[i_subj],
                                                               all_timepoints[i_subj]))
                conved = False
                convedwhen = ''
                convedby = ''
        else:
            print('{0}-{1} couldn\'t be organized.'.format(all_subjects[i_subj],
                                                           all_timepoints[i_subj]))
            note = files_note
            orged = False
            orgedwhen = ''
            orgedby = ''
            print('{0}-{1} couldn\'t be converted.'.format(all_subjects[i_subj],
                                                           all_timepoints[i_subj]))
            conved = False
            convedwhen = ''
            convedby = ''

        df = add_subject(df, all_subjects[i_subj],
                         all_timepoints[i_subj], orged, orgedwhen, orgedby,
                         conved, convedwhen, convedby, note)

    df = df[columns]
    df.to_csv(csv_file, index=False)


if __name__ == '__main__':
    """
    If you call this function from the shell, the arguments are assumed
    to be the raw data directory, the organization csv file, and the
    task's param_file, in that order.
    """
    main(sys.argv[1], sys.argv[2], sys.argv[3])
