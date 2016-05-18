#pragma once
//

//  mongoExpSub1Runner.hpp
//
//  Created by Nick Hathaway on 2015/08/18.
//  Copyright (c) 2015 Nick Hathaway. All rights reserved.
//

#include "mongoExpSub1SetUp.hpp"

namespace mongoExp {

class mongoExpSub1Runner : public bib::progutils::programRunner {
 public:
  mongoExpSub1Runner();
  
  static int printCollectionDocuments(const bib::progutils::CmdArgs & inputCommands);
  static int printDatabases(const bib::progutils::CmdArgs & inputCommands);
  //
  static int mongoTest2(const bib::progutils::CmdArgs & inputCommands);
};
} // namespace mongoExp
