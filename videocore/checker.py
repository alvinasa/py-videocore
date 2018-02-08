from videocore.vinstr import *
from videocore.encoding import Register

# helper functions

def print_with_indent(instr):
  print ('    {}'.format(instr))

def print_with_attension(instr):
  print ('>>> {}'.format(instr))

# TODO: print labels
# labels are not stored in asm._instructions, but asm._labels (tuple label with its position)
def print_instructions(instrs, indexes, labels):
  labels_rev = enc.rev (labels)
  for index in indexes:
    if 0 <= index <= len(instrs) - 1:
      l = labels_rev.get(index)
      if l:
        print_with_indent ('L.{}'.format(l))
      print_with_indent(instrs[index])

def print_around(target, instrs, labels):
  index = instrs.index(target)
  labels_rev = enc.rev (labels)
  print_instructions(instrs, range (index-2, index), labels)
  l = labels_rev.get(index)
  if l:
    print_with_indent('L.{}'.format(l))
  print_with_attension(target)
  print_instructions(instrs, range (index+1, index + 3), labels)

#================ utility functions ===================================

def is_tmu(reg):
  assert (isinstance (reg, Register))
  return 56 <= reg.addr <= 63

def is_sfu(reg):
  assert (isinstance (reg, Register))
  return 52 <= reg.addr <= 55

def is_sfu_instruction(instr):
  assert (isinstance (instr, InstrBase))
  outputs = get_outputs(instr)
  for output in outputs:
    if is_sfu(output):
      return True
  return False

def get_outputs(instr):
  outputs = []
  if is_composed (instr):
    outputs.append (instr.add_instr.get_dst())
    outputs.append (instr.mul_instr.get_dst())
  elif instr.get_dst():
    outputs.append (instr.get_dst())
  return filter (lambda x: x != None, outputs)

def get_inputs(instr):
  inputs = []
  if is_composed (instr):
    inputs.append(instr.add_instr.get_arg1())
    inputs.append(instr.add_instr.get_arg2())
    inputs.append(instr.mul_instr.get_arg1())
    inputs.append(instr.mul_instr.get_arg2())
  else:
    inputs.append(instr.get_arg1())
    inputs.append(instr.get_arg2())
  return filter (lambda x: x != None, inputs)

# return instruction if instr is located in the position of last delay-slot
def is_in_last_delayslot (instr, instrs, labels):
  index = instrs.index(instr)
  if index - 3 < 0:
    return None

  prev = instrs[index - 3]
  if is_branch(prev):
    return instrs[labels[prev.target.name]]
  else:
    return None

#================ check functions ======================================

def check_branch_delay_slot(instr, instrs, labels):
  f = True
  if (is_branch (instr)):
    index = instrs.index(instr)
    if len(instrs) < index + 3:
      print ('warning: instructions of delay_slot is short?')
      print_around(instr, instrs, labels)
      f = False
    else:
      delay_slot = instrs[index+1:index+4]

      for item in delay_slot:
        if (is_branch (item)):
          print ('warning: branch is located in the position of delay_slot')
          print_around(item, instrs, labels)
          f = False

  return f

def check_composed(instr, instrs, labels):
  if (is_composed(instr)):
    v = instr
    if v.add_instr.dst == v.mul_instr.dst and v.add_instr.sig != 'thread end':
      print ('warning: dst is the same register in the following composed-instruction')
      print_around(instr, instrs, labels)
      return False
  return True

def check_signal(instr, instrs, labels):
  f = True
  if not (is_composed (instr) or is_add (instr) or is_mul (instr)):
    return True

  outputs = get_outputs (instr)
  sig = instr.get_sig()

  if sig and (sig == 'load tmu0' or sig == 'load tmu1'):
    for out in outputs:
      if is_tmu(out):
        print ('warning: signal to tmu and setting tmu register are together')
        print_around(instr, instrs, labels)

        f = False
  return f

def check_regfile(instr, instrs, labels):
  f = True
  index = instrs.index(instr)

  if len(instrs) == index + 1:
    return True

  # prev -> current
  prev = instr
  current = is_in_last_delayslot(instr, instrs, labels)
  show_current = True

  if current:
    pass
  else:
    show_current = False
    current = instrs[index + 1]

  outputs = get_outputs(prev)
  inputs = get_inputs(current)

  for out in outputs:
    for read in inputs:
      if enc.GENERAL_PURPOSE_REGISTERS.get(out.name, None) and  out.name == read.name:
        print ('warning: regfile is read next to writing instruction')
        print_around(prev, instrs, labels)
        if show_current:
          print('-----------------')
          print_around(current, instrs, labels)
        f = False

  return f

def get_nexts(instr, instrs, labels, n):
  index = instrs.index(instr)
  if n == 0:
    return [instr]

  l = []
  n1 = is_in_last_delayslot(instr, instrs, labels)
  if n1:
    l.append(n1)

  if index + 1 < len(instrs):
    n2 = instrs[index+1]
    l.append(n2)

  if l:
    l = map(lambda insn: get_nexts (insn, instrs, labels, n-1), l)
    return list(reduce(lambda x, y: x + y, l))
  else:
    return []

single_steps = [check_regfile, check_composed, check_branch_delay_slot, check_signal]

def single_step(instrs, labels):
  f = True
  for instr in instrs:
    for check in single_steps:
      f = f and check (instr, instrs, labels)
  return f

all_checks = [single_step]

def extract_verbose(instr):
  return instr.verbose

def prepare(instrs, labels):
  instrs = list (map(extract_verbose, instrs))
  labels = dict (map (lambda x: (x[0].name, x[1]), filter (lambda p: p[0].pinned, labels)))
  return (instrs, labels)

def check_main(instrs, labels):
  instrs, labels = prepare(instrs, labels)
  f = True
  # print_instructions (instrs, range (0, len (instrs)), labels)
  for check in all_checks:
    f = f and check(instrs, dict (labels))
  return f
