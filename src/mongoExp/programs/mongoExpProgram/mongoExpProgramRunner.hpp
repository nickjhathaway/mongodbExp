#pragma once
//

//  mongoExpProgramRunner.hpp
//
//  Created by Nick Hathaway on 2015/08/18.
//  Copyright (c) 2015 Nick Hathaway. All rights reserved.
//

#include "mongoExpProgramSetUp.hpp"

namespace mongoExp {

class mongoExpProgramRunner : public bib::progutils::oneRing {
 public:
  mongoExpProgramRunner();
  
  static int hellowWorldMain(std::map<std::string, std::string> inputCommands);

};
} // namespace mongoExp
