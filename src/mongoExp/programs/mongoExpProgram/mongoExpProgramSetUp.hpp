#pragma once
//

//  mongoExpProgramSetUp.hpp
//
//  Created by Nick Hathaway on 2015/08/18.
//  Copyright (c) 2015 Nick Hathaway. All rights reserved.
//
#include <bibcpp.h>

namespace mongoExp {

class mongoExpProgramSetUp : public bib::progutils::ProgramSetUp {

 public:
    using ProgramSetUp::ProgramSetUp; //include programSetUp's constructors
};
} // namespace mongoExp

//bib::progutils::programSetUp
