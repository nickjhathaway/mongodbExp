#pragma once
//

//  mongoExpProgramRunner.hpp
//
//  Created by Nick Hathaway on 2015/08/18.
//  Copyright (c) 2015 Nick Hathaway. All rights reserved.
//

#include "mongoExpProgramSetUp.hpp"

namespace mongoExp {

class mongoExpProgramRunner : public bib::progutils::OneRing {
 public:
  mongoExpProgramRunner();
  
  static int hellowWorldMain(const bib::progutils::CmdArgs & inputCommands);

};
} // namespace mongoExp
