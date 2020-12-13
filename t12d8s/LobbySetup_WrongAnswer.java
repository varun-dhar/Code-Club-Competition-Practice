/*
 ____              _______  ______   ______   ___   _______  ___   _______  __    _ 
|    |            |   _   ||      | |      | |   | |       ||   | |       ||  |  | |
 |   |    ____    |  |_|  ||  _    ||  _    ||   | |_     _||   | |   _   ||   |_| |
 |   |   |____|   |       || | |   || | |   ||   |   |   |  |   | |  | |  ||       |
 |   |            |       || |_|   || |_|   ||   |   |   |  |   | |  |_|  ||  _    |
 |   |            |   _   ||       ||       ||   |   |   |  |   | |       || | |   |
 |___|            |__| |__||______| |______| |___|   |___|  |___| |_______||_|  |__|

*/

import java.util.Scanner;


public class LobbySetup_WrongAnswer {

  static int lobbySetup (int numPlayers) {
    if (numPlayers < 4)
      return -1;
    
    return 0;
  }

  public static void main(String[] args) {
    runProgram();
  }
























  //
  // Below is the code to take input & run your method.
  //
  // No touchy!!
  //

  static int numCases;

  static int[] input_lobbySizes;  // input
  static int[] out_numImposters;  // algo output


  static void runProgram () {
    takeInput();
    runTestCases();
  }


  static void takeInput () {
    Scanner sc = new Scanner(System.in);

    System.out.print("Number cases: ");

    // Initialize Algo Inputs
    numCases = sc.nextInt();
    input_lobbySizes = new int[numCases];
    out_numImposters = new int[numCases];

    sc.nextLine();
    for (int i=0; i<numCases; i++) {
      System.out.println("Case #" + (i+1));
      System.out.print("> ");

      // Actually take case input
      input_lobbySizes[i] = sc.nextInt();
    }

    sc.close();
  }


  static void runTestCases () {
    System.out.println("======= Results ========");

    for (int i=0; i<numCases; i++) {
      int in_lobbySize = input_lobbySizes[i];
      String caseString = "[case] \n" + in_lobbySize + "\n[case_end] \n";
      System.out.print(caseString);

      int o_numImps = lobbySetup(in_lobbySize);
      out_numImposters[i] = o_numImps;

      String resultString = "[result] \n" + o_numImps + "\n[result_end] \n";
      System.out.print(resultString);
      System.out.println();
    }
  }

}
