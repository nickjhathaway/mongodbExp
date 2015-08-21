
//  mongoExpSub2Runner.cpp
//
//  Created by Nick Hathaway on 2015/08/18.
//  Copyright (c) 2015 Nick Hathaway. All rights reserved.
//

    
#include "mongoExpSub2Runner.hpp"
    
    
namespace mongoExp {

mongoExpSub2Runner::mongoExpSub2Runner()
    : bib::progutils::programRunner({addFunc("hellowWorld2", hellowWorld2, false)},
                    "mongoExpSub2") {}
                    
int mongoExpSub2Runner::hellowWorld2(std::map<std::string, std::string> inputCommands) {
  mongoExpSub2SetUp setUp(inputCommands);
  std::string name = "World";
  setUp.setOption(name, "--name", "Someone's Name");
  setUp.finishSetUp(std::cout);
  std::cout << "From mongoExpSub2 hellowWorld2, Hello " << name << "!" << std::endl;
  return 0;
}
                    
} // namespace mongoExp
