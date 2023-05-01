#!/usr/bin/env python3

import os
import re
import cantools
from cantools.subparsers import generate_c_source
import argparse
from types import SimpleNamespace

FULL_FILE_HEADER_FMT='''
#pragma once
{include_file}
{struct_define}
{struct_parse}
{struct_unpack}
'''    

FULL_FILE_BODY_FMT='''
{include_file}
{struct_parse}
{struct_unpack}
'''   

STRUCT_DEFINE_FMT='''
struct {struct_name} {{
    {member}
    
    {struct_name}(){{
        {fun_init}
    }}

    void print(){{
        //Serial.println(\"{struct_name}:\");
        {fun_print};
    }}  
}};
'''
 
STRUCT_PARSE_HEADER_FMT='''
    int PARSE_{message_name_upper}(const can_frame& can, T_{message_name_upper}& data);
'''

STRUCT_PARSE_FMT='''
    int PARSE_{message_name_upper}(const can_frame& can, T_{message_name_upper}& data) {{
        if ({space_name_upper}_{message_name_upper}_FRAME_ID != can.can_id){{
            return 1;
        }}

        {space_name}_{message_name_lower}_t tmp;
        if (0 != {space_name}_{message_name_lower}_unpack(&tmp, can.data, can.can_dlc)){{
            return 2;
        }}

        {fun_parse}

        return 0;
    }}
'''

STRUCT_UNPACK_HEADER_FMT='''
    void UNPACK_{space_name_upper}(const can_frame& can, bool to_print);
'''

STRUCT_UNPACK_FMT='''
    void UNPACK_{space_name_upper}(const can_frame& can, bool to_print) {{
        int ret = 0;
        {fun_unpack}
    }}
'''

def _canonical(value):
    """Replace anything but 'a-z', 'A-Z' and '0-9' with '_'.
    """
    return re.sub(r'[^a-zA-Z0-9]', '_', value)


def camel_to_snake_case(value):
    value = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', value)
    value = re.sub(r'(_+)', '_', value)
    value = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', value).lower()
    value = _canonical(value)

    return value

class build_dbc_cpp_wrap():
    def __init__(self, work_dir, out_dir, namespace_prefix):
        self.work_dir = work_dir
        self.out_dir = out_dir
        self.namespace_prefix = namespace_prefix
        self.dbc_pairs = []
        self.include_files = []
        self.struct_defines = []

    def insert_dbc_pair(self, root, name):
        dbc = os.path.join(root, name)
        nm = "{}".format(os.path.basename(name).split(".")[0])
        v = (nm, dbc)
        self.dbc_pairs.append(v)

    def walk_dbc_files(self):
        self.dbc_pairs = []
        # If work directory is already a .dbc file use it directly
        if self.work_dir.endswith(".dbc"):
            self.insert_dbc_pair(".", self.work_dir)
        else:
            for root, dirs, files in os.walk(self.work_dir, topdown=False):
                for name in files:
                    if name.endswith(".dbc"):
                        self.insert_dbc_pair(root, name)

    def run_can_tools(self):
        toKeep = []
        for namespace, dbcpath in self.dbc_pairs:
            args = SimpleNamespace(encoding=None, prune=False, no_strict=True, node=None, infile=dbcpath, no_floating_point_numbers=False, bit_fields=False, generate_fuzzer=False, use_float=True, database_name=None, output_directory=self.out_dir)
            try:
                generate_c_source._do_generate_c_source(args)
                toKeep.append((namespace, dbcpath))
            except Exception as e:
                print(e)

        self.dbc_pairs = toKeep

    def get_include_files(self):
        lines = ["#include <mcp2515.h>\n"]
        for namespace, dbcpath in self.dbc_pairs:
            inc = "#include \"{}.h\"".format(namespace)
            lines.append(inc)
        lines.append("")
        return ''.join(lines)

    def getDB(self, dbcPath):
        try:
            return cantools.database.load_file(dbcPath)        
        except cantools.database.errors.Error as e:
            print(e)
            return None

    def get_struct_defines(self):
        lines = []
        for namespace, dbcpath in self.dbc_pairs:
            db = self.getDB(dbcpath)
            if db is None:
                    continue
   
            for message in  db.messages:
                message_name = camel_to_snake_case(message.name)
            
                signal_names = []
                member_lines = []
                init_lines = []
                print_lines = []
                for signal in message.signals:
                    signal_name = camel_to_snake_case(signal.name)
                    member_line = 'float {};'.format(signal_name.upper())
                    init_line = '{} = 0;'.format(signal_name.upper())
                    member_lines.append(member_line)
                    init_lines.append(init_line)
                    signal_names.append(signal_name)

                struct_name_txt = 'T_{}'.format(message_name.upper())
                member_txt = ''.join(member_lines)
                fun_init_txt = ''.join(init_lines)
                fun_print_txt = ''.join(print_lines)

                line = STRUCT_DEFINE_FMT.format(struct_name=struct_name_txt,member=member_txt,fun_init=fun_init_txt,fun_print=fun_print_txt)      
                lines.append(line)

        return ''.join(lines)

    def get_struct_parses(self, decl_only = False):
        lines = []
        for namespace, dbcpath in self.dbc_pairs:
            db = self.getDB(dbcpath)
            if db is None:
                    continue            
            
            for message in  db.messages:
                message_name = camel_to_snake_case(message.name)                   
            
                if decl_only:
                    line = STRUCT_PARSE_HEADER_FMT.format(message_name_upper=message_name.upper())
                else:               
                    parse_lines = []
                    for signal in message.signals:
                        signal_name = camel_to_snake_case(signal.name)                     
                        
                        parse_line = 'data.{0} = {1}_{2}_{3}_decode(tmp.{3});\n'.format(signal_name.upper(), namespace, message_name.lower(), signal_name.lower())                     
                        parse_lines.append(parse_line)

                    fun_parse_txt = ''.join(parse_lines)  
                    line = STRUCT_PARSE_FMT.format(                                            
                                                space_name=namespace, 
                                                space_name_upper=namespace.upper(),
                                                message_name_lower=message_name.lower(),
                                                message_name_upper=message_name.upper(), 
                                                fun_parse=fun_parse_txt)       
                lines.append(line)

        return ''.join(lines)


    def get_struct_unpacks(self, decl_only = False):
        lines = []
        for namespace, dbcpath in self.dbc_pairs:
            if decl_only:
                line = STRUCT_UNPACK_HEADER_FMT.format(space_name_upper=namespace.upper())
            else:
                db = self.getDB(dbcpath)
                if db is None:
                        continue            
                
                unpack_messages = []
                for message in  db.messages:
                    message_name = camel_to_snake_case(message.name)    

                    unpack_message = '''
                    T_{message_name_upper} _{message_name_lower};                
                    ret = PARSE_{message_name_upper}(can, _{message_name_lower});
                    if(0==ret){{
                        if (to_print) {{
                            _{message_name_lower}.print();
                        }}                    
                    }} else if (1==ret) {{
                    }} else if (2==ret) {{
                        //Serial.println("struct  T_{message_name_upper} data parse error."); 
                    }} 
                    '''.format(message_name_lower=message_name.lower(), message_name_upper=message_name.upper())
                    unpack_messages.append(unpack_message)
                line = STRUCT_UNPACK_FMT.format(space_name_upper=namespace.upper(), fun_unpack=''.join(unpack_messages))

            lines.append(line)

        return ''.join(lines)
          
    def write_files(self):
        all_cpp = FULL_FILE_BODY_FMT.format(
            include_file='#include "' + self.namespace_prefix + '.h"',
            struct_parse=self.get_struct_parses(),
            struct_unpack=self.get_struct_unpacks())

        all_header = FULL_FILE_HEADER_FMT.format(
            include_file = self.get_include_files(),
             struct_define=self.get_struct_defines(),
              struct_parse=self.get_struct_parses(True),
              struct_unpack=self.get_struct_unpacks(True))

        with open(os.path.join(self.out_dir, self.namespace_prefix + ".cpp"), "w+") as f:
            f.write(all_cpp)

        with open(os.path.join(self.out_dir, self.namespace_prefix + ".h"), "w+") as f:
            f.write(all_header)

    def run(self):
        self.walk_dbc_files()
        self.run_can_tools()
        self.get_include_files()
        self.write_files()


if __name__ == "__main__" :
    parser = argparse.ArgumentParser(
        prog='DBC-2-CPP-py',
        description='Convert dbc files into C++ files')

    parser.add_argument('input', default=".")
    parser.add_argument('-o', '--output', default=".")
    parser.add_argument('-p', '--prefix', default="CAN_Export")

    args = parser.parse_args()
    wrap = build_dbc_cpp_wrap(args.input, args.output, args.prefix)
    wrap.run()
