#pragma once
//

//  mongoExpProgramSetUp.hpp
//
//  Created by Nick Hathaway on 2015/08/18.
//  Copyright (c) 2015 Nick Hathaway. All rights reserved.
//
#include <bibcpp.h>

namespace mongoExp {

class mongoExpProgramSetUp : public bib::progutils::programSetUp {

 public:
    using programSetUp::programSetUp; //include programSetUp's constructors
};
} // namespace mongoExp
