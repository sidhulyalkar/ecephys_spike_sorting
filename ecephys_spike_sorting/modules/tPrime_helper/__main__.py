from argschema import ArgSchemaParser
import os
import sys
import subprocess
import time
import fnmatch
from pathlib import Path

import numpy as np

from ...common.utils import catGT_ex_params_from_str


def call_TPrime(args):
    # Run TPrime on a "standard" multiprobe + NI, using NP 1.0 or 2.0, with run
    # folder and probe folders
    # inputs:
    # full path to Tprime executable
    # parameters for "to stream" extracted edges ("to stream" = the reference stream for the data set)
    # parameters for NI sync edges
    
    # bNPY, if True, no text files of spike times will be written
    bNPY = True;
    if bNPY:
        outSuffix = '.npy'
    else:
        outSuffix = '.txt'

    print('ecephys spike sorting: TPrime helper module')
    start = time.time()
    
    # build paths to the input data for TPrime
    catGT_dest = args['directories']['extracted_data_directory']
    run_name = args['catGT_helper_params']['run_name'] + '_g' + args['catGT_helper_params']['gate_string']
    run_dir_name = 'catgt_' + run_name
    prb_dir_prefix = run_name + '_imec'
    
    run_directory = os.path.join( catGT_dest, run_dir_name ) # extracted edge files for aux data reside in run directory
    sync_period = args['tPrime_helper_params']['sync_period']
    
    # check for presence of an fyi file, indicating run with catgt 3.0 or later
    fyi_path = run_directory.replace('\\', '/') + '/' + run_name + '_all_fyi.txt'
    fyi_exists = Path(fyi_path).is_file()
    
    if fyi_exists:
        
        toStream_params = args['tPrime_helper_params']['toStream_sync_params']
        toStream_js, toStream_ip = parse_stream(toStream_params)
        toStream_id = (toStream_js, toStream_ip)
        toStream_path, from_list, from_list_ids, events_list, from_stream_index, out_list = parse_catgt_fy(fyi_path, toStream_id)
        
        # if toStream is an imec probe, create the file of spike times in sec
        prb_dir = prb_dir_prefix + str(toStream_ip)
        ks_outdir = 'imec' + str(toStream_ip) + '_ks' + args['kilosort_helper_params']['kilosort2_params']['KSver']        
        st_file = os.path.join(run_directory, prb_dir, ks_outdir, 'spike_times.npy')
        # convert to seconds; if bNPY = True, returned file is an npy file
        # otherwise, text.
        toStream_events_sec = spike_times_npy_to_sec(st_file, 0, bNPY)
        # if data was saved as text, also save as npy
        if not bNPY:
            spike_times_sec_to_npy(toStream_events_sec)
                        
        # loop over the from_list_ids; for any that are probes, need to create 
        # files of spike times, and append to event_list, from_stream_index, and out_list
        for i, id in enumerate(from_list_ids):
            if id[0] == 2:      # imec stream
                prb_dir = prb_dir_prefix + str(id[1])
                ks_outdir = 'imec' + str(id[1]) + '_ks' + args['kilosort_helper_params']['kilosort2_params']['KSver']
                st_file = os.path.join(run_directory, prb_dir, ks_outdir, 'spike_times.npy')
                # convert to seconds; if bNPY = True, returned file is an npy file
                # otherwise, text.
                st_file_sec = spike_times_npy_to_sec(st_file, 0, bNPY)
                events_list.append(st_file_sec)
                from_stream_index.append(i)
                # build path for output spike times text file
                out_name = 'spike_times_sec_adj' + outSuffix
                out_file = os.path.join(run_directory, prb_dir,ks_outdir, out_name)
                out_list.append(out_file)
                         
    else:

        # build list of from streams
        #   all streams for which sync edges have been extracted
    
        toStream_params = args['tPrime_helper_params']['toStream_sync_params']
        ni_sync_params = args['tPrime_helper_params']['ni_sync_params']
        
        ni_ex_string = args['tPrime_helper_params']['ni_ex_list']       
        ni_ex_list = list()
        
        if ni_ex_string != '':
            # find start points all instances of '-X' in ni_ex_string
            ni_str_list = ni_ex_string.split(' ')
            nstr = len(ni_str_list)
            for i in range(nstr):
                firstDash = ni_str_list[i].find('-')
                if firstDash >= 0:
                    print(ni_str_list[i][firstDash+1:])
                    ni_ex_list.append(ni_str_list[i][firstDash+1:])
            # need to get the file name from the directory in case user used the  
            # -1 option to specify the digital channel     
            # extracted ni files are in the run directory
            match_XA_str = run_name + '_tcat.nidq.XA_*.txt'
            match_XD_str = run_name + '_tcat.nidq.XD_*.txt'
            match_iXA_str = run_name + '_tcat.nidq.iXA_*.txt'
            match_iXD_str = run_name + '_tcat.nidq.iXD_*.txt'
            match_times_str = run_name + '_tcat.nidq.times.npy'
            file_list = os.listdir(run_directory)
            ni_ex_files = fnmatch.filter(file_list,match_XA_str) + \
                          fnmatch.filter(file_list,match_XD_str) + \
                          fnmatch.filter(file_list,match_iXA_str) + \
                          fnmatch.filter(file_list,match_iXD_str) + \
                          fnmatch.filter(file_list,match_times_str)
                              
        
        im_ex_string = args['tPrime_helper_params']['im_ex_list']
        im_ex_list = list()
        
        if im_ex_string != '':
            # find start points all instances of '-X' in ni_ex_string
            im_str_list = im_ex_string.split(' ')
            nstr = len(im_str_list)
            for i in range(nstr):
                firstDash = im_str_list[i].find('-')
                if firstDash >= 0:
                    print(im_str_list[i][firstDash+1:])
                    im_ex_list.append(im_str_list[i][firstDash+1:])
        
        
        toStream_type, toStream_prb, toStream_ex_name = catGT_ex_params_from_str(toStream_params)
    
        from_list = list()       # list of files of sync edges for streams to translate to reference
        events_list = list()     # list of files of event times to translate to reference
        from_stream_index = list()     # list of indicies matching event files to a from stream
        out_list = list()    # list of paths for output files, one per event file
        
        c_type, c_prb, ni_sync_ex_name = catGT_ex_params_from_str(ni_sync_params)
    
        if toStream_type == 'SY':
            
            # toStream is a probe stream sync pulse
            # need to get the file name from the directory in case user used the  
            # -1 option to specify the last channel in the file 
            prb_dir = prb_dir_prefix + str(toStream_prb)
            match_str = run_name + '_tcat.imec' + str(toStream_prb) + '.ap.SY_*_6_*.txt'
            file_list = os.listdir(os.path.join(run_directory,prb_dir))
            flt_list = fnmatch.filter(file_list,match_str)
            if len(flt_list) != 1:
                print('No edge file or multiple files for toStream found\n' )
                return              
            toStream_name = flt_list[0]
            
            toStream_path = os.path.join(run_directory, prb_dir, toStream_name)
            
            # convert events in the toStream to sec; they will not be adjusted
            ks_outdir = 'imec' + str(toStream_prb) + '_ks' + args['kilosort_helper_params']['kilosort2_params']['KSver']
            st_file = os.path.join(run_directory, prb_dir, ks_outdir, 'spike_times.npy')
            # convert to seconds; if bNPY = True, returned file is an npy file
            # otherwise, text.
            toStream_events_sec = spike_times_npy_to_sec(st_file, 0, bNPY)
            # if data was saved as text, also save as npy
            if not bNPY:
                spike_times_sec_to_npy(toStream_events_sec)
    
    
    
            # fromStreams will include all other SY + NI if present
    
            # loop over SY, add the sync file to the fromList
            # get extraction parameters, build name for output file
    
            for ex_str in im_ex_list:
                # get params
                c_type, c_prb, c_ex_name = catGT_ex_params_from_str(ex_str) 
                if c_ex_name == toStream_name:
                    continue
                
                # These are imec SYNC channels
                # need to get the file name from the directory in case user used the  
                # -1 option to specify the last channel in the file 
                prb_dir = prb_dir_prefix + str(c_prb)
                match_str = run_name + '_tcat.imec' + str(c_prb) + '.ap.SY_*_6_*.txt'
                file_list = os.listdir(os.path.join(run_directory,prb_dir))
                flt_list = fnmatch.filter(file_list,match_str)
                if len(flt_list) != 1:
                    print('No edge file or multiple files for toStream found\n' )
                    return              
                c_name = flt_list[0]
                 
                from_list.append(os.path.join(run_directory, prb_dir, c_name))
                c_index = len(from_stream_index)
                # build path to spike times npy file
                ks_outdir = 'imec' + str(c_prb) + '_ks' + args['kilosort_helper_params']['kilosort2_params']['KSver']
                st_file = os.path.join(run_directory, prb_dir, ks_outdir, 'spike_times.npy')
                st_file_sec = spike_times_npy_to_sec(st_file, 0, bNPY)
                events_list.append(st_file_sec)
                from_stream_index.append(c_index)
                # build path for output spike times text file
                out_name = 'spike_times_sec_adj' + outSuffix
                out_file = os.path.join(run_directory, prb_dir,ks_outdir, out_name)
                out_list.append(out_file)
        
            # get index for sync channel in NI. If none or not found, no ni
            # edge files will be added to events_list
            matchI = [i for i, value in enumerate(ni_ex_list) if ni_sync_params in value]
            
            if len(matchI) == 1:
                # get params
              
                # build match string to find file of NI sync edges
                # for the digital channel match string uses a wild card
                # '*" character for the word parameter
                c_type, c_prb, c_ex_name = catGT_ex_params_from_str(ni_sync_params)            
                c_name = run_name + '_tcat.nidq.' + c_ex_name + '.txt'
                c_name_match = fnmatch.filter(ni_ex_files, c_name) 
                
                if len(c_name_match) == 1:
                    # add to list of from_files for TPrime
                    from_list.append(os.path.join(run_directory, c_name_match[0]))
                    
                    # remove from list of ni_ex_files. The other files will be added to events list
                    ni_ex_files.remove(c_name_match[0])
                    
                else:
                    print('No match or multiple matches for ni sync file in Tprime_helper.' )           
                
                #index for this from stream
                c_index = len(from_stream_index)
                
                # loop over the remaining files of edges extracted from NI,
                # add to events_list and out_file
                for ex_file in ni_ex_files:
                    # get params
                    events_list.append(os.path.join(run_directory, ex_file))
                    from_stream_index.append(c_index)
                    
                    # get suffix for this file
                    suf = Path(ex_file).suffix
                    ext_pos = ex_file.find(suf)                
                    c_output_name = ex_file[0:ext_pos] + '.adj' + suf              
                    out_file = os.path.join(run_directory, c_output_name)
                    out_list.append(out_file) 
            else:
                print('No NI sync channel found')
    
                    
        else:
            # toStream is NI
            
            # build match string to find file of NI sync edges
            # for the digital channel match string uses a wild card
            # '*" character for the word parameter
            c_type, c_prb, c_ex_name = catGT_ex_params_from_str(ni_sync_params)            
            c_name = run_name + '_tcat.nidq.' + c_ex_name + '.txt'
            flt_list = fnmatch.filter(ni_ex_files, c_name) 
            toStream_name = flt_list[0]
            toStream_path = os.path.join(run_directory, toStream_name)
    
            # build list of event files, include: 
            #   all files of spike times
            #   no NI files, because they are already in the "toStream"
    
            # loop over all SY files
            for ex_str in im_ex_list:
                # get params
                c_type, c_prb, c_ex_name = catGT_ex_params_from_str(ex_str)
                
                # These are imec SYNC channels
                # need to get the file name from the directory in case user used the  
                # -1 option to specify the last channel in the file 
                prb_dir = prb_dir_prefix + str(c_prb)
                match_str = run_name + '_tcat.imec' + str(c_prb) + '.ap.SY_*_6_*.txt'
                file_list = os.listdir(os.path.join(run_directory,prb_dir))
                flt_list = fnmatch.filter(file_list,match_str)
                if len(flt_list) != 1:
                    print('No edge file or multiple files for fromStream found\n' )
                    return              
                c_name = flt_list[0]
               
                from_list.append(os.path.join(run_directory, prb_dir, c_name))
                c_index = len(from_stream_index)
                # build path to spike times npy file
                ks_outdir = 'imec' + str(c_prb) + '_ks' + args['kilosort_helper_params']['kilosort2_params']['KSver']
                st_file = os.path.join(run_directory, prb_dir, ks_outdir, 'spike_times.npy')
                st_file_sec = spike_times_npy_to_sec(st_file, 0, bNPY)
                events_list.append(st_file_sec)
                from_stream_index.append(c_index)
                # build path for output spike times text file
                out_name = 'spike_times_sec_adj' + outSuffix
                out_file = os.path.join(run_directory, prb_dir, ks_outdir, out_name)
                out_list.append(out_file)

    print('toStream:')
    print(toStream_path)
    print('fromStream')
    for fp in from_list:
        print(fp)
    print('event files')
    for i, ep in enumerate(events_list):
        print('index: ' + repr(from_stream_index[i]) + ',' + ep)
    print('output files')
    for op in out_list:
        print(op)
        
    # path to the 'runit.bat' executable that calls TPrime.
    # Essential in linux where TPrime executable is only callable through runit
    if sys.platform.startswith('win'):
        exe_path = os.path.join(args['tPrime_helper_params']['tPrime_path'], 'runit.bat')
    elif sys.platform.startswith('linux'):
        exe_path = os.path.join(args['tPrime_helper_params']['tPrime_path'], 'runit.sh')
    else:
        print('unknown system, cannot run TPrime')   
        
    # Print out command for help with debugging
    tcmd = list()
    tcmd.append(exe_path)
    tcmd.append(' -syncperiod=' + repr(sync_period))
    tcmd.append(' -tostream=' + toStream_path)

    for i, fp in enumerate(from_list):
        tcmd.append(' -fromstream=' + repr(i) + ',' + fp)

    for i, ep in enumerate(events_list):
        tcmd.append(' -events=' + repr(from_stream_index[i]) + ',' + ep + ',' + out_list[i])

    # write out file to record the TPrime command for a record
    bat_path = os.path.join(run_directory, run_name + '_TPrime_cmd.txt')
    with open(bat_path, 'w') as batfile:
        batfile.write(str(tcmd))

        
    # make the TPrime call
    subprocess.Popen(tcmd,shell='False').wait()

    # convert output files were text, convert to npy
    if not bNPY:
        for op in out_list:
            spike_times_sec_to_npy(op)

    execution_time = time.time() - start

    print('total time: ' + str(np.around(execution_time, 2)) + ' seconds')

    return {"execution_time": execution_time}  # output manifest


def call_TPrime_3A(args):

    # call TPrime for 3A data
    # assumes no nidq stream
    # incoming paths are to the catGT output folder; for the toStream and
    # the fromStreams, find the file of extracted edges that matches
    # the toStream_params
    # inputs:
    # full path to Tprime executable
    # path to "toStream" catGT output, plus the "toStream_params"
    # paths to "from stream" catGT output folders
    
    # bNPY, if True, no text files of spike times will be written
    bNPY = True
    if bNPY:
        outSuffix = '.npy'
    else:
        outSuffix = '.txt'

    print('ecephys spike sorting: TPrime helper module')
    start = time.time()

    # for twStream, get the spike events and convert to seconds
    toStream_parent = args['tPrime_helper_params']['toStream_path_3A']
    
    #
    toStream_params = args['tPrime_helper_params']['toStream_sync_params']
    
    c_type, c_prb, c_ex_name = catGT_ex_params_from_str(toStream_params)
    match_str = '*_tcat.imec.ap.' + c_ex_name + '.txt'   # will be used for both toStream and fromStream(s)
    print(toStream_parent)
    print(match_str)
    file_list = os.listdir(toStream_parent)
    flt_list = fnmatch.filter(file_list,match_str)
    if len(flt_list) != 1:
        print('No edge file or multiple files for toStream found\n' )
        return              
    toStream_name = flt_list[0]
    toStream_path = os.path.join(toStream_parent, toStream_name)

    from_list = args['tPrime_helper_params']['fromStream_list_3A']       # list of files of sync edges for streams to translate to reference
    fS_file_list = list()
    events_list = list()     # list of files of event times to translate to reference
    from_stream_index = list()     # list of indicies matching event files to a from stream
    out_list = list()    # list of paths for output files, one per event file

    # convert events in the toStream to sec; they will not be adjusted
    # search the directory the edges file to get the ks2 output
    # get name of ks2 output dir and convert to sec
    ks_outdir = fnmatch.filter(file_list, 'imec_*_ks' + args['kilosort_helper_params']['kilosort2_params']['KSver'])[0]
    st_file = os.path.join(toStream_parent, ks_outdir, 'spike_times.npy')
    toStream_events_sec = spike_times_npy_to_sec(st_file, 0, bNPY)
    # for later data analysis with spike times as sec, also save as npy
    if not bNPY:
        spike_times_sec_to_npy(toStream_events_sec)

    # for each member of from_list, find the edge file in that directory, and
    # adjust only the spike times. For 3A, other digital channels are copies
    # of those in the toStream

    
    for fS_parent in from_list:
        file_list = os.listdir(fS_parent)
        flt_list = fnmatch.filter(file_list,match_str)
        if len(flt_list) != 1:
            print('No edge file or multiple files for fromStream found\n' )
            return              
        fS_name = flt_list[0]
        fS_file_list.append(os.path.join(fS_parent,fS_name))
        ks_outdir = fnmatch.filter(file_list, 'imec_*_ks' + args['kilosort_helper_params']['kilosort2_params']['KSver'])[0]
        st_file = os.path.join(fS_parent, ks_outdir, 'spike_times.npy')
        st_file_sec = spike_times_npy_to_sec(st_file, 0, bNPY)
        events_list.append(st_file_sec)
        c_index = len(from_stream_index)
        from_stream_index.append(c_index)
        # build path for output spike times text file
        out_name = 'spike_times_sec_adj' + outSuffix
        out_file = os.path.join(fS_parent, ks_outdir, out_name)
        out_list.append(out_file)

    # Print out paths for help with debugging
    print('toStream:')
    print(toStream_path)
    print('fromStream')
    for fp in fS_file_list:
        print(fp)
    print('event files')
    for i, ep in enumerate(events_list):
        print('index: ' + repr(from_stream_index[i]) + ',' + ep)
    print('output files')
    for op in out_list:
        print(op)

    # path to the 'runit.bat' executable that calls TPrime.
    # Essential in linux where TPrime executable is only callable through runit
    if sys.platform.startswith('win'):
        exe_path = os.path.join(args['tPrime_helper_params']['tPrime_path'], 'runit.bat')
    elif sys.platform.starstwith('linux'):
        exe_path = os.path.join(args['tPrime_helper_params']['tPrime_path'], 'runit.sh')
    else:
        print('unknown system, cannot run TPrime')  
        
    sync_period = args['tPrime_helper_params']['sync_period']

    tcmd = exe_path + ' -syncperiod=' + repr(sync_period) + \
        ' -tostream=' + toStream_path

    for i, fp in enumerate(fS_file_list):
        tcmd = tcmd + ' -fromstream=' + repr(i) + ',' + fp

    for i, ep in enumerate(events_list):
        tcmd = tcmd + ' -events=' + repr(from_stream_index[i]) + ',' + ep + ',' + out_list[i]

    # write out batch file to call TPrime
    bat_path = os.path.join(toStream_parent, toStream_name + '_TPrime.bat')
    with open(bat_path, 'w') as batfile:
        batfile.write(tcmd)

    # make the TPrime call
    subprocess.call(tcmd)

    # convert output files to npy
    if not bNPY:
        for op in out_list:
            spike_times_sec_to_npy(op)

    execution_time = time.time() - start

    print('total time: ' + str(np.around(execution_time, 2)) + ' seconds')

    return {"execution_time": execution_time}  # output manifest


def spike_times_npy_to_sec(sp_fullPath, sample_rate, bNPY):
    # convert spike_times.npy to text of times in sec
    # return path to the new file. Can take sample_rate as a
    # parameter, or set to 0 to read from param file

    # get file name and create path to new file
    sp_path, sp_fileName = os.path.split(sp_fullPath)
    baseName, bExt = os.path.splitext(sp_fileName)
    if bNPY:
        new_fileName = baseName + '_sec.npy'
    else:
        new_fileName = baseName + '_sec.txt'
        
    new_fullPath = os.path.join(sp_path, new_fileName)

    # load spike_times.npy; returns numpy array (Nspike,) as uint64
    spike_times = np.load(sp_fullPath)

    if sample_rate == 0:
        # get sample rate from params.py file, assuming sp_path is a full set
        # of phy output
        with open(os.path.join(sp_path, 'params.py'), 'r') as f:
            currLine = f.readline()
            while currLine != '':  # The EOF char is an empty string
                if 'sample_rate' in currLine:
                    sample_rate = float(currLine.split('=')[1])
                    print(f'sample_rate read from params.py: {sample_rate:.10f}')
                currLine = f.readline()

            if sample_rate == 0:
                print('failed to read in sample rate\n')
                sample_rate = 30000

    spike_times_sec = spike_times/sample_rate   # spike_times_sec dtype = float

    if bNPY:
        # write out npy file
        np.save(new_fullPath, spike_times_sec)
    else:
        # write out single column text file
        nSpike = len(spike_times_sec)
        with open(new_fullPath, 'w') as outfile:
            for i in range(0, nSpike-1):
                outfile.write(f'{spike_times_sec[i]:.6f}\n')
            outfile.write(f'{spike_times_sec[nSpike-1]:.6f}')

    return new_fullPath


def spike_times_sec_to_npy(spa_fullPath):
    # convert a text file of spike times in seconds to an npy file of
    # python floats, with shape (Nspike,)
    # spa => spikes, adjusted

    # get file name and create path to new file
    spa_path, spa_fileName = os.path.split(spa_fullPath)
    baseName, bExt = os.path.splitext(spa_fileName)
    new_fileName = baseName + '.npy'
    new_fullPath = os.path.join(spa_path, new_fileName)

    # count lines in file to size array
    lineCount = 0
    with open(os.path.join(spa_fullPath), 'r') as f:
        for line in f:
            lineCount = lineCount + 1

    times = np.zeros((lineCount,), dtype='float')
    # read in text file, single column of floats
    i = 0
    with open(os.path.join(spa_fullPath), 'r') as f:
        for line in f:
            times[i] = float(line)
            i = i + 1

    np.save(new_fullPath, times)
    
def parse_stream(stream_str):
    # stream_str is the stream name followed by the index (e.g. imec3)
    # stream type indicies (js): 0 = ni, 1 = obx, 2 = imec    
    if stream_str.find('ni') > -1:
        js = 0
        ip = 0 # never more than one ni stream
    elif stream_str.find('obx') > -1:
        js = 1
        ip = int(stream_str.partition('obx')[2])
    elif stream_str.find('imec') > -1:
        js = 2
        ip = int(stream_str.partition('imec')[2])
    else:
        js = -1
        ip = -1
    return js, ip  
        
    
    
def parse_catgt_fy(fyi_path, toStream_id):

    # read fyi file, build array of paths to sync files 
    # toStream_id is the tuple (js,ip) for the toStream
    # return 
    #   toStream_path
    #   from_list = list of paths to sync edge files for each from stream
    #   event_list = list of event edges in the fyi file
    #   fron_stream_index = list of from stream indicies for fyi events files
    #   out_list = paths for output for fyi events files
    #          
    
    # create empty lists to fill in
    from_list = []
    from_list_ids = []
    events_list = []
    from_stream_index = []
    out_list = []
   
    with open(fyi_path, 'r') as reader:
        line = reader.readline()
        while line != '':  # The EOF char is an empty string
            
            stream_str, eq, curr_path = line.partition("=")
            stream_str = stream_str.partition('_')[2]
            
            if line.find('sync') == 0:                
                # this is the path to a file of sync edges
                curr_path = curr_path[0:len(curr_path)-1] # trim off cr on end
                js, ip = parse_stream(stream_str)
                if (js,ip) == toStream_id:
                    toStream_path = curr_path
                else:
                    from_list_ids.append((js,ip))
                    from_list.append(curr_path)
  
            elif line.find('times') == 0:
                # this is the path to a file of event edges
                # if it is not from the toStream, add to events, and out_list
                curr_path = curr_path[0:len(curr_path)-1] # trim off cr on end
                js, ip = parse_stream(stream_str)
                if (js,ip) != toStream_id:
                    events_list.append(curr_path)
                    from_stream_index.append(from_list_ids.index((js,ip)))
                    cp = Path(curr_path)
                    curr_output_name = cp.stem + '.adj' + cp.suffix            
                    out_list.append(os.path.join(cp.parent, curr_output_name))
            line = reader.readline()   
         
    return toStream_path, from_list, from_list_ids, events_list, from_stream_index, out_list


def main():

    from ._schemas import InputParameters, OutputParameters

    """Main entry point:"""
    mod = ArgSchemaParser(schema_type=InputParameters,
                          output_schema_type=OutputParameters)

    if mod.args['tPrime_helper_params']['tPrime_3A']:
        output = call_TPrime_3A(mod.args)
    else:
        output = call_TPrime(mod.args)

    output.update({"input_parameters": mod.args})
    if "output_json" in mod.args:
        mod.output(output, indent=2)
    else:
        print(mod.get_output_json(output))


if __name__ == "__main__":
    main()
