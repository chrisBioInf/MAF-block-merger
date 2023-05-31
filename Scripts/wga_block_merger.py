#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar 14 09:52:16 2023

@author: christopher
"""


import sys
import os
from Bio import AlignIO, Seq
from Bio.Align import MultipleSeqAlignment
import numpy as np
from scipy import stats
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt


THIS_DIR = os.path.dirname(os.path.abspath(__file__))

if THIS_DIR not in sys.path:
    sys.path.append(THIS_DIR)

from maf_to_gtf import maf_to_gtf


alignment_file = sys.argv[1]
block_length_threshold = 1000
species_consensus_threshold = 0.75
block_distance_threshold = 0
offset_threshold = 0


def print_alignment_simple(records):
    for i in range(0, len(records)):
        print(records[i].id)
        print(str(records[i].seq))


def plot_merge_summary(records, merged_records, merged_blocks_n):
    lengths = []
    blocks = []
    seq_ns = []
    
    for record in records:
        lengths.append(len(record[0].seq))
        blocks.append("Pre-Merge")
        seq_ns.append(len(record))
    for record in merged_records:
        lengths.append(len(record[0].seq))
        seq_ns.append(len(record))
        blocks.append("Post-Merge")
    
    data= {
        "Length": lengths,
        "Merge status": blocks,
        "Number of species": seq_ns,
        "Merged blocks": merged_blocks_n,
        }
    fig, ax = plt.subplots(2, 2, figsize=(9, 8))
    sns.countplot(data=data, x="Merge status", edgecolor='k', ax=ax[0][0], width=0.5)
    ax[0][0].set_ylabel("Count")
    sns.boxplot(data=data, x="Merge status", y="Length", ax=ax[0][1])
    ax[0][1].set_ylabel("Length [nt]")
    ax[0][1].plot([-1, 2], [block_length_threshold, block_length_threshold], 'k--')
    ax[0][1].set_yscale("log")
    sns.boxplot(data=data, x="Merge status", y="Number of species", ax=ax[1][0], width=0.5)
    ax[1][0].set_ylabel("Number of Species")
    sns.histplot(data=data, x="Merged blocks", stat='probability', ax=ax[1][1])
    ax[1][1].set_ylabel("Probability")
    plt.savefig("%s_merge.pdf" % alignment_file, dpi=300, bbox_inches="tight")
    plt.savefig("%s_merge.svg" % alignment_file, dpi=300, bbox_inches="tight")


def print_similarity_matrix(matrix, records):
    record_labels = [str(record.id) for record in records]
    similarity_columns = {}
    
    for i in range(0, len(record_labels)):
        similarity_columns[record_labels[i]] = matrix[i]
    
    df = pd.DataFrame(data=similarity_columns, index=similarity_columns).round(4)
    start, end = records[i].annotations["start"], records[i].annotations["start"] + records[i].annotations["size"]
    df.to_csv("Similarity_matrices/dmel_%s_%s.tsv" % (start, end), sep="\t")
    return df
    

def load_alignment_file(filename):
    handle = AlignIO.parse(handle=open(filename, 'r'), format="maf")
    alignments = [align for align in handle]
    return alignments


def write_alignments(alignments, filename):
    AlignIO.write([MultipleSeqAlignment(records=records) for records in alignments], 
                  handle=open(filename + ".merged", 'w'), 
                  format="maf")


def coordinate_distance(end1, start2):
    return start2 - end1


def pairwise_sequence_identity(seq1, seq2):
    count = 0
    for i in range(0, len(seq1)):
        if seq1[i] == seq2[i]:
            count += 1
    return count / len(seq1)
    

def local_species_consensus(block1, block2):
    block1_ids = set([str(seq.id) for seq in block1])
    block2_ids = set([str(seq.id) for seq in block2])
    consensus_score  = (len(block1_ids.intersection(block2_ids)) + len(block2_ids.intersection(block1_ids))) / (len(block1_ids) + len(block2_ids))
    return consensus_score


def concat_with_bridge(seq1, seq2, offset):
    seq_ = Seq.Seq(str(seq1) + "N"*offset + str(seq2)) 
    return seq_


def fill_bridges_with_gaps(records):
    length_dict = {}
    seq_dict = {}
    for i in range(0, len(records)):
        length_dict[str(records[i].id)] = len(records[i].seq)
        seq_dict[str(records[i].id)] = str(records[i].seq)
    longest_seq_key = max(length_dict, key=length_dict.get)
    longest_seq = seq_dict.get(longest_seq_key)
    max_length = length_dict.get(longest_seq)
    
    for i in range(0, len(records)):
        if len(records[i].seq) == max_length:
            continue
        seq = str(records[i].seq)
        seq_ = ""
        j = 0
        
        for n in range(0, len(longest_seq)):
            if longest_seq[n] != "N":
                seq_ = seq_ + seq[j]
                j += 1
            else:
                seq_ = seq_ + "-"
        records[i].seq = Seq.Seq(seq_)
    
    return records


def eliminate_consensus_gaps(records):
    ungapped_seqs = []
    for i in range(0, len(records)):
        seq = str(records[i].seq)
        seq_ = ""
        for c in range(0, len(seq)):
            if seq[c] != "-":
                seq_ = seq_ + seq[c]
                continue
            for j in range(0, len(records)):
                seq_2 = str(records[j].seq)
                if seq_2[c] != "-":
                    seq_ = seq_ + seq[c]
                    break
        ungapped_seqs.append(seq_)
    
    for i in range(0, len(records)):
        records[i].seq = Seq.Seq(ungapped_seqs[i])
    
    return records
    

def filter_by_pairwise_id(records):
    seqs = [str(record.seq) for record in records]
    ids = [str(record.id) for record in records]
    matrix = np.ones(shape=(len(records), len(records)))
    
    for i in range(0, len(records)-1):
        record_ = records[i]
        seq = str(record_.seq)
        id_ = str(record_.id)
        for j in range(i+1, len(records)):
            seq_ = str(records[j].seq)
            pairwise_id = pairwise_sequence_identity(seq, seq_)
            matrix[i][j] = pairwise_id
            matrix[j][i] = pairwise_id
            
    return matrix


def filter_by_seq_length(records):
    length_dict = {str(record.id) : len(record.seq.replace('-', '')) for record in records}
    record_dict = {str(record.id) : record for record in records}
    mu = np.mean([x for x in length_dict.values()])
    std = np.std([x for x in length_dict.values()])
    
    for record in records:
        x = str(record.id)
        if std > 0:
            z = abs(length_dict.get(x) - mu) / std
        else:
            z = 0
        if z > 2:
            record_dict.pop(x)
    
    return [record for record in record_dict.values()]


def merge_blocks(block1, block2):
    block1_ids = [str(record.id) for record in block1]
    block2_ids = [str(record.id) for record in block2]
    
    if len(block1_ids) >= len(block2_ids):
        consensus_blocks = set(block1_ids).intersection(block2_ids)
    else:
        consensus_blocks = set(block2_ids).intersection(block1_ids)
    
    block1_records = [record for record in block1 if record.id in consensus_blocks]
    block2_records = [record for record in block2 if record.id in consensus_blocks]
    merged_records = []
    
    for i in range(0, len(block1_records)):
        record_, record2 = block1_records[i], block2_records[i]
        strand1, strand2 = record_.annotations["strand"], record2.annotations["strand"]
        start1, end1 = record_.annotations["start"], record_.annotations["start"] + record_.annotations["size"]
        start2, end2 = record2.annotations["start"], record2.annotations["start"] + record2.annotations["size"]
        offset = coordinate_distance(end1, start2)
        if (offset > offset_threshold) or (strand1 != strand2):
            continue
        record_.seq = concat_with_bridge(record_.seq, record2.seq, offset)
        record_.annotations["size"] = (end1 - start1) + offset + (end2 - start2)
        merged_records.append(record_)
    merged_records = fill_bridges_with_gaps(merged_records)
    matrix = filter_by_pairwise_id(merged_records)
    # df = print_similarity_matrix(matrix, merged_records)
    record_dict = {str(record.id) : record for record in merged_records}
    
    return merged_records


def check_block_viability(block1, block2):
    merge_flag = True
    reference1 = block1[0]
    reference2 = block2[0]
    start1, end1 = reference1.annotations["start"], reference1.annotations["start"] + reference1.annotations["size"]
    start2, end2 = reference2.annotations["start"], reference2.annotations["start"] + reference2.annotations["size"]
    
    if coordinate_distance(end1, start2) > block_distance_threshold:
        merge_flag = False
    elif reference1.annotations["strand"] != reference2.annotations["strand"]:
        merge_flag = False
    elif (len(reference1.seq) > block_length_threshold) or (len(reference2.seq) > block_length_threshold):
        merge_flag = False
    elif local_species_consensus(block1, block2) < species_consensus_threshold:
        merge_flag = False
    elif reference1.id != reference2.id:
        merge_flag = False
         
    return merge_flag


def main():
    alignments = load_alignment_file(alignment_file)
    merged_alignments = []
    i = 0
    block1 = alignments[0]
    merged_blocks_n = []
    local_merges = 1
    
    length = len(alignments)
    
    while i < length-1:
        print("Scan MAF block: %s / %s" % (i+1, length))
        block2 = alignments[i+1]
        merge_flag = check_block_viability(block1, block2)
        
        if merge_flag == True: 
            block1 = merge_blocks(block1, block2)
            local_merges += 1
            i += 1
        else:
            records = filter_by_seq_length(block1)
            records = eliminate_consensus_gaps(records)
            merged_alignments.append(records)
            merged_blocks_n.append(local_merges)
            i += 1
            local_merges = 1
            block1 = alignments[i]
            
    if merge_flag == False:
        merged_alignments.append(eliminate_consensus_gaps(filter_by_seq_length(alignments[-1])))
            
            
    plot_merge_summary(alignments, merged_alignments, merged_blocks_n)
    write_alignments(merged_alignments, alignment_file)
    

if __name__ == "__main__":
    main()