// ---------------------------------------------------------------------------
// Utilidades de la guia de apertura. No dependen de la build order.
//
// Reglas de XS que hay que respetar (el juego no explica bien los errores):
// - el archivo final tiene que ser ASCII puro: el compilador da un error por
//   cada byte no ASCII, tambien dentro de textos y comentarios. En los textos
//   de este archivo se pueden escribir tildes: build.py las convierte en
//   chr(byte) + chr(byte) con sus bytes UTF-8. Los comentarios, solo ASCII.
// - solo caracteres latinos (a, n con tilde, punto medio, comillas angulares...):
//   los demas simbolos salen como "?" en el panel.
// - return siempre con parentesis: return (x);  (o return; en funciones void)
// - no existen ! ni el menos unario: usar == false y 0 - x
// - el tipo de una operacion lo decide el primer operando: las
//   concatenaciones empiezan siempre por una cadena ("" + numero)
// - todos los parametros llevan valor por defecto
// - una funcion solo puede llamar a funciones definidas antes que ella
// - las cadenas globales no conservan su valor: los textos van en funciones
// - nada de comillas simples ni del signo de porcentaje en los textos
// ---------------------------------------------------------------------------

// Lista reutilizable para xsGetPlayerUnitIds (se crea en la primera llamada).
int gGuiaLista = -1;

// Recuentos del jugador que se esta revisando. Los rellena guiaTomarDatos
// (generada desde la build order) una vez por segundo; el array se crea en guiaIniciar.
int gGuiaDatos = -1;

int guiaDato(int i = 0)
{
    int v = xsArrayGetInt(gGuiaDatos, i);
    return (v);
}

int guiaMin(int a = 0, int b = 0)
{
    if (a < b)
    {
        return (a);
    }
    return (b);
}

// Unidades o edificios de un tipo del jugador, incluidos los cimientos.
// Deja sus IDs en gGuiaLista.
int guiaUnidades(int jugador = 0, int objeto = -1)
{
    gGuiaLista = xsGetPlayerUnitIds(jugador, objeto, gGuiaLista);
    if (gGuiaLista < 0)
    {
        return (0);
    }
    int total = xsArrayGetSize(gGuiaLista);
    return (total);
}

// Edificios terminados de un tipo. Un edificio cuenta como terminado si sus
// puntos de construccion llegan al tiempo de construccion o si tiene la vida
// al maximo (los cimientos empiezan con poca vida y la van ganando).
int guiaTerminados(int jugador = 0, int objeto = -1)
{
    int total = guiaUnidades(jugador, objeto);
    float tiempo = xsGetObjectAttribute(jugador, objeto, cTrainTime);
    float vidaMax = xsGetObjectAttribute(jugador, objeto, cHitpoints);
    int terminados = 0;
    for (k = 0; < total)
    {
        int unidad = xsArrayGetInt(gGuiaLista, k);
        if (xsGetUnitBuildPoints(unidad) >= tiempo)
        {
            terminados++;
        }
        else if (xsGetUnitHitpoints(unidad) >= vidaMax)
        {
            terminados++;
        }
    }
    return (terminados);
}

// Aldeanos vivos del jugador, hagan lo que hagan (recurso 38 del juego).
int guiaAldeanosTotal(int jugador = 0)
{
    int n = xsPlayerAttribute(jugador, 38);
    return (n);
}

int guiaEdad(int jugador = 0)
{
    int edad = xsPlayerAttribute(jugador, cAttributeCurrentAge);
    return (edad);
}

// Estado de una tecnologia: 0 = pendiente, 1 = en cola o investigandose, 2 = terminada.
int guiaEstadoTech(int jugador = 0, int tech = -1)
{
    int estado = xsGetTechState(tech, jugador);
    if (estado == cTechStateDone)
    {
        return (2);
    }
    if (estado == cTechStateResearching)
    {
        return (1);
    }
    if (estado == cTechStateQueued)
    {
        return (1);
    }
    return (0);
}

string guiaTextoEstado(int estado = 0)
{
    if (estado == 2)
    {
        return ("hecha");
    }
    if (estado == 1)
    {
        return ("en curso");
    }
    return ("pendiente");
}

// Segundos de juego como m:ss.
string guiaReloj(int segundos = 0)
{
    int m = segundos / 60;
    int s = segundos - m * 60;
    if (s < 10)
    {
        return ("" + m + ":0" + s);
    }
    return ("" + m + ":" + s);
}

// Diferencia de tiempo legible: "45 s" o "1:05".
string guiaDuracion(int segundos = 0)
{
    if (segundos < 60)
    {
        return ("" + segundos + " s");
    }
    return (guiaReloj(segundos));
}
