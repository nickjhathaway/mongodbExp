
//  mongoExpSub1Runner.cpp
//
//  Created by Nick Hathaway on 2015/08/18.
//  Copyright (c) 2015 Nick Hathaway. All rights reserved.
//

    
#include "mongoExpSub1Runner.hpp"
#include <mongocxx/client.hpp>
#include <mongocxx/database.hpp>
#include <mongocxx/instance.hpp>
#include <mongocxx/collection.hpp>
#include <mongocxx/options/find.hpp>

#include <bsoncxx/builder/stream/document.hpp>
#include <bsoncxx/json.hpp>
#include <bsoncxx/types.hpp>

using bsoncxx::builder::stream::document;
using bsoncxx::builder::stream::open_document;
using bsoncxx::builder::stream::close_document;
using bsoncxx::builder::stream::open_array;
using bsoncxx::builder::stream::close_array;
using bsoncxx::builder::stream::finalize;



namespace mongoExp {


template<typename T>
T && removeAllWhitespace(T && s) {
	s.erase(
			std::remove_if(s.begin(), s.end(),
					[]( char ch ) {return std::isspace<char>( ch, std::locale::classic() );}),
			s.end());
	return std::forward<T>(s);
}

mongoExpSub1Runner::mongoExpSub1Runner()
    : bib::progutils::programRunner({addFunc("printCollectionDocuments", printCollectionDocuments, false),
																     addFunc("printDatabases", printDatabases, false),
																		 addFunc("mongoTest2", mongoTest2, false)},
                    "mongoExpSub1") {}
                    
int mongoExpSub1Runner::printCollectionDocuments(const bib::progutils::CmdArgs & inputCommands) {
  mongoExpSub1SetUp setUp(inputCommands);
  std::string database = "test";
  std::string collection = "restaurants";
  std::string outFilename = "";
  uint32_t port = 27017;
  bool overWrite = false;
  bool append = false;
  bool exitOnFailure = true;
  setUp.setOption(database,   "--database",   "Database name");
  setUp.setOption(collection, "--collection", "Collection name");
  setUp.setOption(port,       "--port",       "Port number of mongod instance");

  setUp.setOption(outFilename,"--outFile",    "Out File name, defautls to stdout");
  setUp.setOption(overWrite,  "--overWrite",  "Whether to over write out file");
  setUp.setOption(append,     "--append",     "Whether to append to out file");
  setUp.finishSetUp(std::cout);
  mongocxx::instance inst{}; //a mongod instance must be around for mongo commands to work;
  mongocxx::client conn{mongocxx::uri{"mongodb://localhost:" + estd::to_string(port)}};   //a client to interact with the mongod instance, defaults to default ports, do mongocxx::client{"mongodb://localhost:27017"} to control port and host


  std::ofstream outFile;
  std::ostream out(bib::files::determineOutBuf(outFile, outFilename, ".json", overWrite, append, exitOnFailure));

  mongocxx::database db = conn[database];   //get the "test" database
  mongocxx::collection col = db[collection];  //a collection in the "test" database
  auto cursor = col.find({}); //all the documents in the "restaurants" collection
  for (auto&& doc : cursor) {

  	out << removeAllWhitespace(bsoncxx::to_json(doc) )<< std::endl;
  }
  return 0;
}



int mongoExpSub1Runner::printDatabases(const bib::progutils::CmdArgs & inputCommands) {
  mongoExpSub1SetUp setUp(inputCommands);
  std::string outFilename = "";
  uint32_t port = 27017;
  bool overWrite = false;
  bool append = false;
  bool exitOnFailure = true;
  setUp.setOption(port,       "--port",       "Port number of mongod instance");

  setUp.setOption(outFilename,"--outFile",    "Out File name, defaults to stdout");
  setUp.setOption(overWrite,  "--overWrite",  "Whether to over write out file");
  setUp.setOption(append,     "--append",     "Whether to append to out file");
  setUp.finishSetUp(std::cout);

  mongocxx::instance inst{}; //a mongod instance must be around for mongo commands to work;
  mongocxx::client conn;
  conn = mongocxx::client{mongocxx::uri{"mongodb://localhost:" + estd::to_string(port)}};   //a client to interact with the mongod instance, defaults to default ports, do mongocxx::client{"mongodb://localhost:27017"} to control port and host

  std::ofstream outFile;
  std::ostream out(bib::files::determineOutBuf(outFile, outFilename, ".json", overWrite, append, exitOnFailure));

  std::shared_ptr<mongocxx::cursor> curs = std::make_shared<mongocxx::cursor>(conn.list_databases());
	Json::Reader reader;

	try {
	  for (auto&& doc : *curs) {
	  	Json::Value root;
	  	auto status =  reader.parse(bsoncxx::to_json(doc),root);
	  	if(status){
	  		out << root<< std::endl;
	  	}else{
	  		out << "Failed to read" << std::endl;
	  	}

	  	out << bsoncxx::to_json(doc) << std::endl;
	  }
	} catch (std::exception & e) {
		std::cerr << e.what() << std::endl;
		exit(1);
	}

  return 0;
}

int mongoExpSub1Runner::mongoTest2(const bib::progutils::CmdArgs & inputCommands) {
  mongoExpSub1SetUp setUp(inputCommands);
  std::string name = "World";
  setUp.setOption(name, "--name", "Someone's Name");
  setUp.finishSetUp(std::cout);
  mongocxx::instance inst{};
  mongocxx::client conn{};

  mongocxx::database db = conn["test"];

  // TODO: fix dates

  // @begin: cpp-insert-a-document
  document restaurant_doc;

  restaurant_doc  << "address" << open_document
          << "street"   << "2 Avenue"
          << "zipcode"  <<  "10075"
          << "building" << "1480"
          << "coord"    << open_array
              << -73.9557413 << 40.7720266 << close_array << close_document
      << "borough"  << "Manhattan"
      << "cuisine"  << "Italian"
      << "grades"   << open_array
          << open_document
              << "date" << bsoncxx::types::b_date{12323}
              << "grade" << "A"
              << "score" << 11 << close_document
          << open_document
              << "date" << bsoncxx::types::b_date{121212}
              << "grade" << "B"
              << "score" << 17 << close_document << close_array
      << "name" << "Vella"
      << "restaurant_id" << "41704620" << finalize;
  mongocxx::collection rCollection = db["restaurants"];
  auto res = rCollection.insert_one(restaurant_doc.view());
  // @end: cpp-insert-a-document
  return 0;
}


                    
} // namespace mongoExp
