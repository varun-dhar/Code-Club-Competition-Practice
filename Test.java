public class Test {

    int testVar;

    public Test(){
        testVar = 123;
    }

    public boolean isWorking(){
        return true;
    }

    public static void main(String[] args){

        Test tester = new Test();

        boolean exVar = false;

        int variableToTest;

        if ( tester.isWorking() ){
            exVar = true;
            variableToTest = 300;
        }

        if ( exVar ){
            System.out.println("You have run me success");
        }

        
    }
}