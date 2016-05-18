#pragma once
//

//  mongoExpSub2Runner.hpp
//
//  Created by Nick Hathaway on 2015/08/18.
//  Copyright (c) 2015 Nick Hathaway. All rights reserved.
//

#include "mongoExpSub2SetUp.hpp"

namespace mongoExp {

class mongoExpSub2Runner : public bib::progutils::programRunner {
 public:
  mongoExpSub2Runner();
  
  static int hellowWorld2(const bib::progutils::CmdArgs & inputCommands);

};
} // namespace mongoExp
