
//  mongoExpProgramRunner.cpp
//
//  Created by Nick Hathaway on 2015/08/18.
//  Copyright (c) 2015 Nick Hathaway. All rights reserved.
//

    
#include "mongoExpProgramRunner.hpp"
    
    
#include "mongoExp/programs/mongoExpSub1/mongoExpSub1Runner.hpp"
#include "mongoExp/programs/mongoExpSub2/mongoExpSub2Runner.hpp"

namespace mongoExp {

mongoExpProgramRunner::mongoExpProgramRunner()
    : bib::progutils::oneRing({addRing(std::make_shared<mongoExpSub1Runner>()),addRing(std::make_shared<mongoExpSub2Runner>()),},{addFunc("hellowWorldMain", hellowWorldMain, false)},
                    "mongoExp") {}
                    
int mongoExpProgramRunner::hellowWorldMain(const bib::progutils::CmdArgs & inputCommands) {
  mongoExpProgramSetUp setUp(inputCommands);
  std::string name = "World";
  setUp.setOption(name, "--name", "Someone's Name");
  setUp.finishSetUp(std::cout);
  std::cout << "From mongoExpProgram hellowWorldMain, Hello " << name << "!" << std::endl;
  return 0;
}
                    
} // namespace mongoExp
