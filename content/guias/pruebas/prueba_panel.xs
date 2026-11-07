// ---------------------------------------------------------------------------
// Prueba 4: panel de varias lineas con un archivo 100 por cien ASCII.
// El compilador XS rechaza cualquier byte no ASCII del codigo (tambien dentro
// de los textos), asi que tildes y simbolos se construyen al ejecutar con chr():
//   variante B (panel de arriba): chr() de cada byte UTF-8, p. ej. chr(195) + chr(173)
//   variante A (panel de abajo, 3 s despues): chr(codigo Unicode), p. ej. chr(237)
// ---------------------------------------------------------------------------

string u2(int b1 = 0, int b2 = 0)
{
    string s = chr(b1) + chr(b2);
    return (s);
}

string u3(int b1 = 0, int b2 = 0, int b3 = 0)
{
    string s = chr(b1) + chr(b2) + chr(b3);
    return (s);
}

// Maqueta del panel nuevo con la variante B.
void pruebaPanelB(int x = 0)
{
    string ia = u2(195, 173);       // i con tilde
    string nn = u2(195, 177);       // enie
    string pu = u2(194, 183);       // punto medio
    string ok = u3(226, 156, 147);  // check
    string fl = u3(226, 150, 182);  // triangulo
    string sep = "  " + pu + "  ";
    string panel = "<YELLOW>Fast Castle 27+2" + sep + "Paso 5 de 16" + sep + "vas 0:12 tarde";
    panel = panel + "\n<GRAY>" + ok + " 3  Campamento maderero y 4 le" + nn + "adores" + sep + "3:12 a tiempo";
    panel = panel + "\n<GRAY>" + ok + " 4  Primer jabal" + ia + sep + "3:41 +11 s";
    panel = panel + "\n<WHITE>" + fl + " 5  Con el aldeano 12, construye una casa y un molino junto a las bayas";
    panel = panel + "\n<GREEN>      Casas 2/3" + sep + "Molino 0/1" + sep + "Recolectores 1/5" + sep + "ref. 5:40";
    panel = panel + "\n<AQUA>   6  Segundo jabal" + ia + " y 14 en comida" + sep + "6:25";
    panel = panel + "\n   7  Segundo campamento maderero y 9 le" + nn + "adores" + sep + "8:35";
    panel = panel + "\n   8  Campamento minero y 3 en el oro" + sep + "9:55   <RED>(rojo a mitad de linea)";
    xsDisplayInstructions(panel, 3600, 1, 68, cPanelTop, false, true, "", -1);
}

// Variante A, aparte por si genera texto invalido.
void pruebaPanelA(int x = 0)
{
    string linea = "<RED>A: Gu" + chr(237) + "a, le" + chr(241) + "adores, check " + chr(10003) + ", triangulo " + chr(9654) + ", punto " + chr(183);
    xsDisplayInstructions(linea, 3600, 1, 70, cPanelBottom, false, false, "", -1);
}

int gPruebaVeces = 0;

rule pruebaRegla
    active
    minInterval 3
    maxInterval 3
{
    gPruebaVeces++;
    if (gPruebaVeces == 1)
    {
        xsChatData("PRUEBA 4: todo compilado, la regla funciona");
        pruebaPanelB(0);
    }
    if (gPruebaVeces == 2)
    {
        pruebaPanelA(0);
    }
}

void main()
{
    xsChatData("PRUEBA 4: main ejecutado");
}
