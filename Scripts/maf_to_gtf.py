#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Feb  9 09:03:11 2023

@author: christopher
"""

import sys

from utility import read_maf

strand_dict = {
    1: "+",
    -1: "-",
    "+": "+",
    "-": "-",
    }


def maf_to_gtf(fs, output):
    seqname = []
    source = []
    type_ = []
    starts = []
    ends = []
    score = []
    strands = []
    frame = []
    descriptor = []
    
    if "window" in fs:
        this_source = "rnazWindow"
    else:
        this_source = "MAF"
    
    handle = read_maf(fs)
    count = 0
    
    for alignment in handle:
        count += 1
        record = alignment[0]
        seqname.append(record.id)
        source.append(this_source)
        type_.append("alignment_block")
        starts.append(record.annotations.get("start"))
        ends.append(record.annotations.get("start") + record.annotations.get("size"))
        score.append(".")
        frame.append(".")
        strands.append(strand_dict.get(record.annotations.get("strand")))
        descriptor.append("Continuously aligned block %s" % count)
        
    if output == "":
        for i in range(0, count):
            line = "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s" % (
                seqname[i], source[i], type_[i], starts[i], ends[i], 
                score[i], strands[i], frame[i], descriptor[i]
                )
            print(line)
    else:
        with open(output, 'w') as f:
            for i in range(0, count):
                line = "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s" % (
                    seqname[i], source[i], type_[i], starts[i], ends[i], 
                    score[i], strands[i], frame[i], descriptor[i]
                    )
                f.write(line + "\n")


def write_to_gtf(parser):
    parser.add_option("-i","--input",action="store",type="string", dest="input",help="The (MAF) input file (Required).")
    parser.add_option("-o","--output",action="store",type="string", default="", dest="out_file",help="GTF file to write to. If empty, coordinates are redirected to stdout.")
    options, args = parser.parse_args()
    
    required = ["input"]
    
    for r in required:
        if options.__dict__[r] == None:
            print("You must pass a --%s argument." % r)
            sys.exit()
    
    maf_to_gtf(options.input, output=options.out_file)

