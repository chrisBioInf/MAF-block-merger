#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar 14 09:52:16 2023

@author: christopher
"""


import sys
from Bio import Seq
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt

from utility import write_maf, read_maf, print_maf_alignment


def plot_merge_summary(records, merged_records, merged_blocks_n, alignment_file, block_length_threshold):
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
    plt.show()


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


def concat_with_bridge(seq1, seq2, offset, max_offset):
    n_gaps = max_offset - offset
    seq_ = Seq.Seq(str(seq1) + "N"*offset + '-'*n_gaps + str(seq2)) 
    return seq_


def eliminate_consensus_gaps(records):
    ungapped_seqs = []
    seq_matrix = np.array([list(record.seq) for record in records])
    for i in range(0, len(records)):
        seq_ = ""
        for c in range(0, len(seq_matrix[i])):
            if seq_matrix[i][c] != "-":
                seq_ = seq_ + seq_matrix[i][c]
                continue
            for j in range(0, len(seq_matrix)):
                if seq_matrix[j][c] != "-":
                    seq_ = seq_ + seq_matrix[i][c]
                    break
        ungapped_seqs.append(seq_)
    
    for i in range(0, len(records)):
        records[i].seq = Seq.Seq(ungapped_seqs[i])
    
    return records


def filter_by_seq_length(records, reference=True):
    length_dict = {str(record.id) : len(record.seq.replace('-', '')) for record in records}
    record_dict = {str(record.id) : record for record in records}
    mu = np.mean([x for x in length_dict.values()])
    std = np.std([x for x in length_dict.values()])
    
    count = 0
    
    for record in records:
        count += 1
        if (count == 1) and reference:
            continue
        
        x = str(record.id)
        if std > 0:
            z = abs(length_dict.get(x) - mu) / std
        else:
            z = 0
        if z > 2:
            record_dict.pop(x)
    
    return [record for record in record_dict.values()]


def merge_blocks(block1, block2, reference=True, offset_threshold=0):
    block1_ids = [str(record.id) for record in block1]
    block2_ids = [str(record.id) for record in block2]
    
    if len(block1_ids) >= len(block2_ids):
        consensus_blocks = set(block1_ids).intersection(block2_ids)
    else:
        consensus_blocks = set(block2_ids).intersection(block1_ids)
    
    block1_records = [record for record in block1 if record.id in consensus_blocks]
    block2_records = [record for record in block2 if record.id in consensus_blocks]
    merged_records = []
    offsets = []
    
    for i in range(0, len(block1_records)):
        offsets.append( coordinate_distance(block1_records[i].annotations["start"] + block1_records[i].annotations["size"]
                                            ,block2_records[i].annotations["start"] ))
    max_offset = max(offsets)
    
    for i in range(0, len(block1_records)):
        record_, record2 = block1_records[i], block2_records[i]
        strand1, strand2 = record_.annotations["strand"], record2.annotations["strand"]
        start1, end1 = record_.annotations["start"], record_.annotations["start"] + record_.annotations["size"]
        start2, end2 = record2.annotations["start"], record2.annotations["start"] + record2.annotations["size"]
        offset = offsets[i]
        if ((offset > offset_threshold) or (strand1 != strand2)):
            continue
        record_.seq = concat_with_bridge(record_.seq, record2.seq, offset, max_offset)
        record_.annotations["size"] = (end1 - start1) + offset + (end2 - start2)
        merged_records.append(record_)
    
    return merged_records


def check_block_viability(block1, block2, species_consensus_threshold, block_distance_threshold, block_length_threshold):
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


def merge(parser):
    parser.add_option("-i","--input",action="store",type="string", dest="input",help="The (MAF) input file (Required).")
    parser.add_option("-o", "--output", action="store", type="string", dest="out_file", default="", help="MAF file to write to. If empty, results alignments are redirected to stdout.")
    parser.add_option("-r", "--reference", action="store", default=True, dest="reference", help="Should the first sequence always be considered the reference? (Default: True)")
    parser.add_option("-s", "--species-consensus", action="store", type="float", default=0.75, dest="species_consensus", help="Minimal consensus between neighboring blocks for merging (Default: 0.75).")
    parser.add_option("-d", "--max-distance", action="store", default=0, type="int", dest="distance", help="Maximum distance between genomic coordinates of sequences for merging of neighboring blocks (Default: 0).")
    parser.add_option("-l", "--max-length", action="store", default=1000, type="int", dest="length", help="Merged alignment blocks will not be extended past this block length (Default: 1000).")
    parser.add_option("-p", "--plotting", action="store", default=False, dest="plotting", help="Plot a graphic summary of merge results and save to file named [input file].svg (Default: False).")
    options, args = parser.parse_args()
    
    required = ["input"]
    
    for r in required:
        if options.__dict__[r] == None:
            print("You must pass a --%s argument." % r)
            sys.exit()
    
    alignments = read_maf(options.input)
    merged_alignments = []
    block1 = next(alignments)
    merged_blocks_n = []
    local_merges = 1
    
    while block1 != None:
        block2 = next(alignments, None)
        
        if block2 == None:
            # records = filter_by_seq_length(block1, options.reference)
            records = eliminate_consensus_gaps(block1)
            merged_blocks_n.append(local_merges)
            if options.out_file == "":
                print_maf_alignment(records)
            else:
                merged_alignments.append(records)
            break
                
        merge_flag = check_block_viability(block1, block2, 
                                           options.species_consensus,
                                           options.distance,
                                           options.length)
        if merge_flag == True: 
            block1 = merge_blocks(block1, block2, options.reference, 
                                  offset_threshold=options.distance)
            local_merges += 1
        else:
            # records = filter_by_seq_length(block1, options.reference)
            records = eliminate_consensus_gaps(block1)
            merged_blocks_n.append(local_merges)
            local_merges = 1
            block1 = block2
            if options.out_file == "":
                print_maf_alignment(records)
            else:
                merged_alignments.append(records)
                
    if options.plotting == True:
        plot_merge_summary(read_maf(options.input), merged_alignments, merged_blocks_n, options.input, options.length)
    
    if options.out_file != "":
        write_maf(merged_alignments, options.out_file)
    
    